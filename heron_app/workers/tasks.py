import logging
from celery.utils.log import get_task_logger

# Suppress overly verbose logs
logging.getLogger("tenacity").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("PyCardano").setLevel(logging.ERROR)

from heron_app.workers.worker import celery
from heron_app.db.database import SessionLocal
from heron_app.db.models.transaction import Transaction
from heron_app.db.models.transaction_output import TransactionOutput
from heron_app.db.models.transaction_output_asset import TransactionOutputAsset
from heron_app.db.models.transaction_mint import TransactionMint
from heron_app.db.models.minting_policies import MintingPolicy  # noqa: F401
from heron_app.db.models.wallet import Wallet

from blockfrost import BlockFrostApi, ApiUrls
from pycardano import (
    crypto, ExtendedSigningKey, TransactionInput, TransactionOutput as CardanoTxOutput,
    TransactionBody, TransactionWitnessSet, VerificationKeyWitness, fee, Value, MultiAsset,
    Transaction as CardanoTransaction, Address, BlockFrostChainContext, min_lovelace_post_alonzo,
    Metadata, AlonzoMetadata, AuxiliaryData, AssetName, ScriptHash, Asset, TransactionBuilder,UTxO, datum_hash, PlutusData, PaymentSigningKey, SigningKey, VerificationKeyHash, NativeScript, ScriptPubkey, ScriptAll
)

from pycardano.plutus import RawPlutusData, Datum

import cbor2
from typing import Any, Dict, List, Union, Mapping, Optional

import hashlib
from pycardano.exception import TransactionFailedException, InsufficientUTxOBalanceException, UTxOSelectionException
from heron_app.utils.cardano import TransactionSubmitError, ValueNotConservedError, BadInputsError, GenericSubmitError

from cryptography.fernet import Fernet
import os
import json
import traceback
from datetime import datetime
import time
from collections import defaultdict


logger = get_task_logger(__name__)
logger.setLevel(logging.INFO)
if not logger.hasHandlers():
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.propagate = True

WALLET_UTXO_CACHE = {}
MAX_FEE = 0

def enqueue_transaction(transaction_id):
    session = SessionLocal()
    tx = session.query(Transaction).filter(Transaction.id == transaction_id).first()
    if tx:
        wallet = tx.wallet_id
        queue_name = f"wallet_{str(wallet)}"
        process_transaction.apply_async(args=[transaction_id], queue=queue_name)
    session.close()

def get_utxos_from_cache(address):
    return WALLET_UTXO_CACHE.get(address, [])

def set_utxos_to_cache(address, utxo_list):
    WALLET_UTXO_CACHE[address] = utxo_list

def reload_utxos(address):
     
    network = os.getenv("network", "mainnet")
    base_url = ApiUrls.preprod.value if network == "testnet" else ApiUrls.mainnet.value
    api = BlockFrostApi(project_id=os.getenv("BLOCKFROST_PROJECT_ID"), base_url=base_url)

    page = 1
    all_utxos = []

    while True:
        raw_utxos = api.address_utxos(address=address, count=100, page=page)
        if not raw_utxos:
            break

        for utxo in raw_utxos:
            entry = {
                "tx_hash": utxo.tx_hash,
                "tx_index": utxo.tx_index,
                "amounts": {amt.unit: int(amt.quantity) for amt in utxo.amount}
            }
            all_utxos.append(entry)

        if len(raw_utxos) < 100:
            break  # No more pages
        page += 1

    set_utxos_to_cache(address, all_utxos)



def dict_to_datum(obj: dict) -> RawPlutusData:
    def convert(o):
        if isinstance(o, dict):
            return {convert(k): convert(v) for k, v in o.items()}
        elif isinstance(o, list):
            return [convert(i) for i in o]
        elif isinstance(o, str):
            return o.encode("utf-8")  # Convert strings to bytes
        elif isinstance(o, (int, bytes)):
            return o
        else:
            raise TypeError(f"Unsupported type in datum: {type(o)}")

    if "version" in obj and isinstance(obj["version"], int) and obj["version"] > 0:
        version = obj["version"]
        del obj["version"]
    elif "version" in obj and isinstance(obj["version"], str):
        try:
            version = int(obj["version"])
            del obj["version"]
        except ValueError:
            logger.warning(f"Invalid version format in datum: {obj['version']}, defaulting to 1")
            version = 1
    else:
        version = 1


    converted = convert(obj)


    tag121_construct = cbor2.CBORTag(121, [converted, version])


    return RawPlutusData(tag121_construct)


@celery.task(name="heron_app.workers.tasks.process_transaction", bind=True)
def process_transaction(self, transaction_id):

    logger.info(f"Processing transaction {transaction_id}")

    session = SessionLocal()
    try:
        tx = session.query(Transaction).filter(Transaction.id == transaction_id).first()
        if not tx:
            return
        wallet = session.query(Wallet).filter(Wallet.id == tx.wallet_id).first()
        if not wallet:
            tx.status = "failed"
            session.commit()
            return

        address = wallet.address
        available_utxos = get_utxos_from_cache(address)

        if len(available_utxos) == 0:
            logger.info(f"No cached UTXOs found for wallet {wallet.id} ({address}), fetching from Blockfrost")
            reload_utxos(address)
            available_utxos = get_utxos_from_cache(address)
            if len(available_utxos) == 0:
                logger.error(f"No UTXOs found for wallet {wallet.id} ({address}), cannot process transaction {transaction_id}")
                raise BadInputsError(f"No UTXOs found for wallet {wallet.id} ({address})")

        logger.debug(f"Available UTXOs for wallet {wallet.id} ({address}): {available_utxos}")
        
        fernet = Fernet(os.getenv("WALLET_ENCRYPTION_KEY"))
        mnemonic = fernet.decrypt(wallet.encrypted_root_key.encode()).decode()
        root_key = crypto.bip32.HDWallet.from_mnemonic(mnemonic)
        payment_key = root_key.derive_from_path("m/1852'/1815'/0'/0/0")
        payment_skey = ExtendedSigningKey.from_hdwallet(payment_key)

        network = os.getenv("network", "mainnet")
        context = BlockFrostChainContext(
            project_id=os.getenv("BLOCKFROST_PROJECT_ID"),
            base_url=ApiUrls.preprod.value if network == "testnet" else ApiUrls.mainnet.value,
        )


        MAX_FEE = context.protocol_param.min_fee_constant + (context.protocol_param.max_tx_size * context.protocol_param.min_fee_coefficient)

        logger.debug(f"Max fee: {MAX_FEE}")



        outputs_db = session.query(TransactionOutput).filter(TransactionOutput.transaction_id == tx.numeric_id).all()
        assets_needed = {}

        builder = TransactionBuilder(context)

        assets_needed["lovelace"] = MAX_FEE

        print(f"Assets needed: {assets_needed}")

        for out in outputs_db:
            val = Value(0)
            ma = MultiAsset()
            assets = session.query(TransactionOutputAsset).filter(TransactionOutputAsset.output_id == out.id).all()
            for asset in assets:

                if asset.unit == "lovelace":
                    val.coin += int(asset.quantity)
                    if "lovelace" not in assets_needed:
                        assets_needed["lovelace"] = 0
                    assets_needed["lovelace"] += val.coin
                else:
                    policy_id = asset.unit[:56]
                    asset_name_hex = asset.unit[56:]
                    policy = ScriptHash.from_primitive(policy_id)
                    asset_name = AssetName(bytes.fromhex(asset_name_hex))
                    if policy not in ma:
                        ma[policy] = Asset()
                    ma[policy][asset_name] = int(asset.quantity)

                    if asset.unit not in assets_needed:
                        assets_needed[asset.unit] = 0
                    assets_needed[asset.unit] += int(asset.quantity)        


            if ma:
                val.multi_asset = ma
                min_ada_required = min_lovelace_post_alonzo(CardanoTxOutput(Address.from_primitive(out.address), val), context)

                if val.coin < min_ada_required:
                    logger.debug(f"Output {out.id} has insufficient ADA for assets, adjusting to minimum required: {min_ada_required}")
                    if "lovelace" not in assets_needed:
                        assets_needed["lovelace"] = 0
                    assets_needed["lovelace"] = assets_needed["lovelace"] - val.coin + min_ada_required
                    val.coin = min_ada_required


            if out.datum and isinstance(out.datum, dict):


                inline_datum = dict_to_datum(out.datum)


                builder.add_output(CardanoTxOutput(
                    Address.from_primitive(out.address),
                    val,
                    datum=inline_datum
                ))

            else:
                logger.debug(f"Adding output without inline datum.")

                builder.add_output(CardanoTxOutput(
                    Address.from_primitive(out.address),
                    val
                ))

        mints = session.query(TransactionMint).filter(TransactionMint.transaction_id == tx.numeric_id).all()

        if mints:
            logger.debug(f"Found {len(mints)} mints for transaction {transaction_id}")

            # We'll accumulate quantities per (policy_id, asset_name)
            policy_ids = {}

            for mint in mints:
                logger.info(f"Mint request: {mint.policy_id}.{mint.asset_name} × {mint.quantity}")

                if mint.policy_id not in policy_ids:
                    policy_ids[mint.policy_id] = {}

                if mint.asset_name not in policy_ids[mint.policy_id]:
                    policy_ids[mint.policy_id][mint.asset_name] = 0

                policy_ids[mint.policy_id][mint.asset_name] += int(mint.quantity)



            # Build the MultiAsset and the list of native_scripts
            multi_asset = MultiAsset()
            native_scripts = []

            logger.info(f"policy_ids: {policy_ids}")

            for policy_id in policy_ids:
                # fetch & decrypt your signing key for this policy
                mp = session.query(MintingPolicy).filter_by(policy_id=policy_id).first()
                if not mp:
                    raise BadInputsError(f"Unknown policy {policy_id}")
                
                logger.info(f"Processing policy {policy_id}")
                logger.info(f"Processing assets {policy_ids[policy_id]}")

                # prepare the minting script

                fernet = Fernet(os.getenv("WALLET_ENCRYPTION_KEY"))
                skey_cbor_hex = fernet.decrypt(mp.encrypted_policy_skey.encode()).decode("utf8")
                policy_skey = PaymentSigningKey.from_cbor(skey_cbor_hex)


                script = ScriptAll([ScriptPubkey(policy_skey.to_verification_key().hash())])


                if script not in native_scripts:
                    native_scripts.append(script)

                # prepare an Asset map under this policy
                asset_map = Asset()
                # find all assets under this policy
                for asset in policy_ids[policy_id]:

                    name = AssetName(asset.encode("utf-8"))
                    qty = policy_ids[policy_id][asset]
                    asset_map[name] = qty

                multi_asset[ScriptHash.from_primitive(policy_id)] = asset_map

            # finally, attach to the builder
            builder.mint = multi_asset
            builder.native_scripts = native_scripts


        logger.debug("Finding assets in available UTXOs to cover transaction outputs...")
        logger.debug(f"Available UTXOs: {len(available_utxos)}")
        logger.debug(f"Available UTXOs: {available_utxos}")
        logger.debug(f"Assets needed: {assets_needed}")

        while len(available_utxos) > 0 and len(assets_needed) > 1:

            if len(assets_needed) == 1 and "lovelace" in assets_needed:
                break
          
            for unit, qty in assets_needed.items():

                if unit == "lovelace":
                    continue

   
                policy_id = unit[:56]
                asset_name_hex = unit[56:]
                policy = ScriptHash.from_primitive(policy_id)
                asset_name = AssetName(bytes.fromhex(asset_name_hex))
                for utxo in available_utxos:
                    if unit in utxo["amounts"]:
                        tx_input = TransactionInput.from_primitive([utxo["tx_hash"], utxo["tx_index"]])

                        val = Value(0)
                        ma = MultiAsset()

                        val.coin += utxo["amounts"]["lovelace"]
                        
                        if "lovelace" in assets_needed:
                            assets_needed['lovelace'] -= utxo["amounts"]["lovelace"]

                        for utxo_unit, amount in utxo["amounts"].items():
                            if utxo_unit == "lovelace":
                                continue

                            policy_id = utxo_unit[:56]
                            asset_name_hex = utxo_unit[56:]
                            policy = ScriptHash.from_primitive(policy_id)
                            asset_name = AssetName(bytes.fromhex(asset_name_hex))



                            if policy not in ma:
                                ma[policy] = Asset()
                            ma[policy][asset_name] = int(utxo["amounts"][utxo_unit])
                            if utxo_unit in assets_needed:
                                assets_needed[utxo_unit] -= utxo["amounts"][utxo_unit]

                            if ma:
                                val.multi_asset = ma
                      
                        available_utxos.remove(utxo)

                        builder.add_input(UTxO(tx_input, CardanoTxOutput(Address.from_primitive(address), val)))


                        if assets_needed[unit] <= 0:    
                            break

            assets_needed = {k: v for k, v in assets_needed.items() if v > 0}

        
        if len(available_utxos) == 0 and len(assets_needed) > 1:
            logger.error(f"Not enough UTXOs available to cover transaction {transaction_id} outputs")
            raise InsufficientUTxOBalanceException(f"Not enough UTXOs available to cover transaction {transaction_id} outputs")
        
        while len(available_utxos) > 0 and len(assets_needed) > 0 and 'lovelace' in assets_needed and assets_needed['lovelace'] > 0:

            logger.debug(f"Assets needed: {assets_needed}")

            max_ada_utxo = None
            max_ada = 0
            for utxo in available_utxos:
                if utxo["amounts"]["lovelace"] > max_ada:
                    max_ada_utxo = utxo
                    max_ada = utxo["amounts"]["lovelace"]
            if max_ada_utxo:
                logger.debug(f"Selected UTXO {max_ada_utxo['tx_hash']} with {max_ada} ADA")
                tx_input = TransactionInput.from_primitive([max_ada_utxo["tx_hash"], max_ada_utxo["tx_index"]])
                val = Value(0)
                val.coin += max_ada_utxo["amounts"]["lovelace"]

                for unit, amount in max_ada_utxo["amounts"].items():
                    if unit == "lovelace":
                        continue

                    policy_id = unit[:56]
                    asset_name_hex = unit[56:]
                    policy = ScriptHash.from_primitive(policy_id)
                    asset_name = AssetName(bytes.fromhex(asset_name_hex))
                    if policy not in val.multi_asset:
                        val.multi_asset[policy] = Asset()
                    val.multi_asset[policy][asset_name] = max_ada_utxo["amounts"][unit]

                builder.add_input(UTxO(tx_input, CardanoTxOutput(Address.from_primitive(address), val)))
                available_utxos.remove(max_ada_utxo)
                logger.debug(f"Added UTXO {max_ada_utxo['tx_hash']} with amounts: {max_ada_utxo['amounts']}")
                assets_needed['lovelace'] -= max_ada_utxo["amounts"]["lovelace"]
            
            assets_needed = {k: v for k, v in assets_needed.items() if v > 0}

        if len(available_utxos) == 0 and len(assets_needed) > 1:
            logger.error(f"Not enough UTXOs available to cover transaction {transaction_id} outputs")
            raise InsufficientUTxOBalanceException(f"Not enough UTXOs available to cover transaction {transaction_id} outputs")

        if tx.metadata_json:
            try:
                # If it's a string, parse it, otherwise use it directly
                metadata_raw = tx.metadata_json

                logger.debug(f"Metadata raw: {metadata_raw}")
                logger.debug(f"Metadata type: {type(metadata_raw)}")

                if isinstance(metadata_raw, str):
                    metadata_raw = json.loads(metadata_raw)

                metadata_dict = {int(k): v for k, v in metadata_raw.items()}
                auxiliary_data = AuxiliaryData(AlonzoMetadata(metadata=Metadata(metadata_dict)))
                builder.auxiliary_data = auxiliary_data

            except Exception as e:
                logger.warning(f"Metadata error: {e}")

        signers = []
        signers.append(payment_skey)

        if mints:
            for mint in mints:

                policy_details = session.query(MintingPolicy).filter(MintingPolicy.policy_id == mint.policy_id).first()

                if policy_details:
                    fernet = Fernet(os.getenv("WALLET_ENCRYPTION_KEY"))
                    skey_cbor_hex = fernet.decrypt(policy_details.encrypted_policy_skey.encode()).decode("utf8")

                    logger.info(f"Payment signing key: {payment_skey}")
                    logger.info(f"Payment verification key: {payment_skey.to_verification_key()}")
                    logger.info(f"skey_cbor_hex: {skey_cbor_hex}")

                    policy_skey = PaymentSigningKey.from_cbor(skey_cbor_hex)

                    logger.info(f"policy_skey: {policy_skey}")

                    if policy_skey not in signers:
                        signers.append(policy_skey)



        try:

            logger.info(f"signers: {signers}")


            final_tx = builder.build_and_sign(signers, change_address=address)
        except (InsufficientUTxOBalanceException, UTxOSelectionException) as e:
            logger.debug(f"Insufficient UTXO balance for transaction {transaction_id}")

            max_ada_utxo = None
            max_ada = 0
            for utxo in available_utxos:
                if utxo["amounts"]["lovelace"] > max_ada:
                    max_ada_utxo = utxo
                    max_ada = utxo["amounts"]["lovelace"]

            if max_ada_utxo:
                logger.debug(f"Selected UTXO {max_ada_utxo['tx_hash']} with {max_ada} ADA")
                tx_input = TransactionInput.from_primitive([max_ada_utxo["tx_hash"], max_ada_utxo["tx_index"]])
                val = Value(0)
                val.coin += max_ada_utxo["amounts"]["lovelace"]

                for unit, amount in max_ada_utxo["amounts"].items():
                    if unit == "lovelace":
                        continue

                    policy_id = unit[:56]
                    asset_name_hex = unit[56:]
                    policy = ScriptHash.from_primitive(policy_id)
                    asset_name = AssetName(bytes.fromhex(asset_name_hex))
                    if policy not in val.multi_asset:
                        val.multi_asset[policy] = Asset()
                    val.multi_asset[policy][asset_name] = max_ada_utxo["amounts"][unit]
                
                if "lovelace" in assets_needed:
                    assets_needed['lovelace'] -= max_ada_utxo["amounts"]["lovelace"]

                builder.add_input(UTxO(tx_input, CardanoTxOutput(Address.from_primitive(address), val)))
                available_utxos.remove(max_ada_utxo)
                logger.debug(f"Added UTXO {max_ada_utxo['tx_hash']} with amounts: {max_ada_utxo['amounts']}")
                
                try:
                    final_tx = builder.build_and_sign(signers, change_address=address)
                except (InsufficientUTxOBalanceException, UTxOSelectionException) as e:
                    logger.debug(f"Insufficient UTXO balance for transaction {transaction_id}")
                    raise InsufficientUTxOBalanceException(f"Insufficient UTXO balance for transaction {transaction_id}") from e
            else:
                logger.error(f"No UTXOs available to cover transaction {transaction_id}")
                raise InsufficientUTxOBalanceException(f"No UTXOs available to cover transaction {transaction_id}")
            
        final_body = final_tx.transaction_body


        logger.info(f"Final transaction body: {final_body}")    

        logger.info(f"Data hash: {final_body.script_data_hash}")

    
        logger.info(f"final_tx: {final_tx}")

        try:
            tx_hash = context.submit_tx(final_tx.to_cbor())
            logger.info(f"Transaction {tx.id} submitted successfully: {tx_hash}")

        except TransactionFailedException as tfe:
            error_json = str(tfe)
            # logger.error(f"Transaction submission failed: {error_json}")

            if "BadInputsUTxO" in error_json:
                raise ValueNotConservedError("Value not conserved between inputs and outputs.") from tfe
            elif "ValueNotConservedUTxO" in error_json:
                raise BadInputsError("Bad or spent input UTXO detected.") from tfe
            else:
                logger.error(f"Unhandled submit error: {error_json}")
                raise GenericSubmitError("Unhandled submit error occurred.") from tfe
            

        tx.status = "submitted"
        tx.error_message = None
        tx.tx_hash = tx_hash
        tx.tx_fee = final_body.fee
        tx.tx_size = len(final_tx.to_cbor())
        tx.updated_at = datetime.utcnow()
        session.commit()

        new_utxos = []

        logger.debug(f"Available UTXOs: {len(available_utxos)}")
        logger.debug(f"Available UTXOs: {available_utxos}")

        for i, output in enumerate(final_tx.transaction_body.outputs):
            if output.address == Address.from_primitive(address):
                amounts = {"lovelace": output.amount.coin}
                if output.amount.multi_asset:
                    for policy_id, assets in output.amount.multi_asset.items():
                        for asset_name, qty in assets.items():
                            unit = policy_id.to_primitive().hex() + asset_name.to_primitive().hex()
                            amounts[unit] = qty
                new_utxos.append({
                    "tx_hash": tx_hash,
                    "tx_index": i,
                    "amounts": amounts
                })


        logger.debug(f"len new_utxos: {len(new_utxos)}")
        logger.debug(f"new_utxos: {new_utxos}")


        available_utxos.extend(new_utxos)
        set_utxos_to_cache(address, available_utxos)

        logger.debug(f"Available UTXOs: {len(available_utxos)}")
        logger.debug(f"Available UTXOs: {available_utxos}")

    except ValueNotConservedError as e:
        logger.error(f"Transaction {transaction_id} failed due to value not conserved: {str(e)}")
        tx.status = "queued"
        tx.error_message = str(e)
        tx.retries += 1
        tx.updated_at = datetime.utcnow()
        session.commit()
        enqueue_transaction(transaction_id)

    except BadInputsError as e:
        logger.error(f"Transaction {transaction_id} failed due to bad inputs: {str(e)}")
        tx.status = "queued"
        tx.retries += 1
        tx.error_message = str(e)
        tx.updated_at = datetime.utcnow()
        session.commit()

        time.sleep(60)
        reload_utxos(address)
        enqueue_transaction(transaction_id)

    except GenericSubmitError as e:
        logger.error(f"Transaction {transaction_id} failed due to generic submit error: {str(e)}")

        if tx.retries <= 5:
            tx.status = "queued"
            tx.retries += 1
            session.commit()
            enqueue_transaction(transaction_id)
        else:
            tx.status = "failed"
            tx.error_message = str(e)
            tx.updated_at = datetime.utcnow()
            session.commit()

    except InsufficientUTxOBalanceException as e:
        logger.error(f"Transaction {transaction_id} failed due to insufficient UTXO balance: {str(e)}")

        if tx.retries <= 5:
            tx.status = "queued"
            tx.retries += 1
            session.commit()
            enqueue_transaction(transaction_id)
        else:
            tx.status = "failed"
            tx.error_message = str(e)
            tx.updated_at = datetime.utcnow()
            session.commit()

    except Exception as e:
        logger.error(f"Transaction {transaction_id} failed: {str(e)}")
        logger.error(traceback.format_exc())
     
        if tx.retries <= 5:
            tx.status = "queued"
            tx.retries += 1
            session.commit()
            enqueue_transaction(transaction_id)
        else:
            tx.status = "failed"
            tx.error_message = str(e)
            tx.updated_at = datetime.utcnow()
            session.commit()

    finally:
        session.close()
        logger.info(f"Finished processing transaction {transaction_id}")
