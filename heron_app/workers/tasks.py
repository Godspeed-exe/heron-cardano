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
from heron_app.db.models.wallet import Wallet

from blockfrost import BlockFrostApi, ApiUrls
from pycardano import (
    crypto, ExtendedSigningKey, TransactionInput, TransactionOutput as CardanoTxOutput,
    TransactionBody, TransactionWitnessSet, VerificationKeyWitness, fee, Value, MultiAsset,
    Transaction as CardanoTransaction, Address, BlockFrostChainContext, min_lovelace_post_alonzo,
    Metadata, AlonzoMetadata, AuxiliaryData
)

import hashlib

from pycardano.exception import TransactionFailedException
from heron_app.utils.cardano import TransactionSubmitError, ValueNotConservedError, BadInputsError, GenericSubmitError

from cryptography.fernet import Fernet
import os
import json
import traceback
from datetime import datetime
import time


logger = get_task_logger(__name__)

logger.setLevel(logging.INFO)  # or DEBUG

if not logger.hasHandlers():
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

logger.propagate = True


WALLET_UTXO_CACHE = {}

def enqueue_transaction(transaction_id):

    session = SessionLocal()
    tx = session.query(Transaction).filter(Transaction.id == transaction_id).first()
    if tx:
        wallet = tx.wallet_id
        queue_name = f"wallet_{str(wallet)}"
        process_transaction.apply_async(args=[transaction_id], queue=queue_name)
    session.close()

def get_utxo_cache_key(address):
    return f"utxos:{address}"

def get_utxos_from_cache(address):
    return WALLET_UTXO_CACHE.get(address, [])

def set_utxos_to_cache(address, utxo_list):
    WALLET_UTXO_CACHE[address] = utxo_list

def reload_utxos(address):
    network = os.getenv("network", "mainnet")
    base_url = ApiUrls.preprod.value if network == "testnet" else ApiUrls.mainnet.value
    api = BlockFrostApi(project_id=os.getenv("BLOCKFROST_PROJECT_ID"), base_url=base_url)
    logger.debug(f"Reloading UTXOs from Blockfrost for {address}")
    raw_utxos = api.address_utxos(address)

    result = []
    for utxo in raw_utxos:
        entry = {
            "tx_hash": utxo.tx_hash,
            "tx_index": utxo.tx_index,
            "amounts": {amt.unit: int(amt.quantity) for amt in utxo.amount}
        }
        result.append(entry)

    set_utxos_to_cache(address, result)
    logger.debug(f"Cached {len(result)} UTXOs for {address}")

@celery.task(name="heron_app.workers.tasks.process_transaction", bind=True)
def process_transaction(self, transaction_id):
    session = SessionLocal()
    logger.info(f"Started processing transaction {transaction_id}")

    try:
        tx = session.query(Transaction).filter(Transaction.id == transaction_id).first()
        if not tx:
            logger.warning(f"Transaction {transaction_id} not found.")
            return

        wallet = session.query(Wallet).filter(Wallet.id == tx.wallet_id).first()
        if not wallet:
            tx.status = "failed"
            session.commit()
            return

        address = wallet.address
        logger.info(f"Using wallet address: {address}")
        lock_key = f"utxo-lock:{address}"

        available_utxos = get_utxos_from_cache(address)
        if not available_utxos:
            reload_utxos(address)
            available_utxos = get_utxos_from_cache(address)

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

        outputs_db = session.query(TransactionOutput).filter(TransactionOutput.transaction_id == tx.numeric_id).all()
        output_objs = []
        total_assets_needed = {}

        for out in outputs_db:
            assets_db = session.query(TransactionOutputAsset).filter(TransactionOutputAsset.output_id == out.id).all()
            val = Value(0)
            ma = MultiAsset()
            for asset in assets_db:
                if asset.unit == "lovelace":
                    val.coin += int(asset.quantity)
                else:
                    ma[asset.policy_id][asset.asset_name] = int(asset.quantity)
                    total_assets_needed.setdefault(asset.policy_id, {}).setdefault(asset.asset_name, 0)
                    total_assets_needed[asset.policy_id][asset.asset_name] += int(asset.quantity)
            if len(ma) > 0:
                val.multi_asset = ma
            output_objs.append(CardanoTxOutput(Address.from_primitive(out.address), val))

        total_lovelace_needed = sum([o.amount.coin for o in output_objs]) + 200_000
        selected_utxos = []
        total_input = Value(0)
        consumed_utxos = []

        for utxo in available_utxos:
            tx_input = TransactionInput.from_primitive([utxo['tx_hash'], utxo['tx_index']])
            selected_utxos.append(tx_input)
            consumed_utxos.append(utxo)

            amounts = utxo["amounts"]
            for unit, qty in amounts.items():
                if unit == "lovelace":
                    total_input.coin += qty
                else:
                    policy_id, asset_name = unit[:56], unit[56:]
                    total_input.multi_asset[policy_id][asset_name] += qty

            if total_input.coin >= total_lovelace_needed:
                logger.debug(f"Found sufficient UTXOs: {total_input.coin} >= {total_lovelace_needed}")
                break

        available_utxos = [u for u in available_utxos if u not in consumed_utxos]

        logger.debug(f"Selected UTXOs: {selected_utxos}")
        logger.debug(f"Total input: {total_input}")
        logger.debug(f"Total lovelace needed: {total_lovelace_needed}")
        logger.debug(f"Total assets needed: {total_assets_needed}")
        if total_input.coin < total_lovelace_needed:
            raise Exception(f"Insufficient ADA: {total_input.coin} ")

        output_value = sum([o.amount for o in output_objs], Value(0))
        change = total_input - output_value
        provisional_outputs = output_objs + [CardanoTxOutput(Address.from_primitive(address), change)]
        dummy_fee = 1_000_000

        auxiliary_data = None
        if tx.metadata_json:
            try:
                raw_metadata = json.loads(tx.metadata_json) if isinstance(tx.metadata_json, str) else tx.metadata_json

                # Convert top-level keys back to int
                metadata_dict = {int(k): v for k, v in raw_metadata.items()}

                auxiliary_data = AuxiliaryData(AlonzoMetadata(metadata=Metadata(metadata_dict)))
                aux_hash = hashlib.blake2b(auxiliary_data.to_cbor(), digest_size=32).digest()
                logger.info(f"Including metadata: {metadata_dict}")
            except Exception as e:
                logger.warning(f"Failed to parse or attach metadata: {e}")

        draft_body = TransactionBody(inputs=selected_utxos, outputs=provisional_outputs, fee=dummy_fee)
        if auxiliary_data:
            draft_body.auxiliary_data_hash = aux_hash

        dummy_witness = TransactionWitnessSet(
            vkey_witnesses=[
                VerificationKeyWitness(payment_skey.to_verification_key(), b'\0' * 64)
            ]
        )
        draft_tx = CardanoTransaction(draft_body, dummy_witness, auxiliary_data=auxiliary_data)

        tx_size = len(draft_tx.to_cbor())
        actual_fee = fee(context, tx_size)
        logger.debug(f"Estimated accurate fee: {actual_fee}")

        final_change = total_input - output_value - actual_fee
        if final_change.coin < 0:
            raise Exception("Insufficient ADA to cover fee")

        final_outputs = output_objs
        if final_change.coin > 0 or final_change.multi_asset:
            change_output = CardanoTxOutput(Address.from_primitive(address), final_change)
            min_required = min_lovelace_post_alonzo(change_output, context)
            if final_change.coin >= min_required:
                final_outputs.append(change_output)
            else:
                logger.warning(f"Change too small to include: {final_change.coin} < {min_required}. Adding to fee instead.")
                actual_fee += final_change.coin
                final_change = Value(0)

        final_body = TransactionBody(inputs=selected_utxos, outputs=final_outputs, fee=actual_fee)
        if auxiliary_data:
            final_body.auxiliary_data_hash = aux_hash

        sig = payment_skey.sign(final_body.hash())
        witness = TransactionWitnessSet(vkey_witnesses=[VerificationKeyWitness(payment_skey.to_verification_key(), sig)])
        final_tx = CardanoTransaction(final_body, witness, auxiliary_data=auxiliary_data)

        logger.info(f"Final transaction size: {len(final_tx.to_cbor())} bytes")

        try:
            tx_hash = context.submit_tx(final_tx.to_cbor())
            logger.info(f"Transaction {tx.id} submitted successfully: {tx_hash}")

        except TransactionFailedException as tfe:
            error_json = str(tfe)
            logger.error(f"Transaction submission failed: {error_json}")

            if "ValueNotConservedUTxO" in error_json:
                raise ValueNotConservedError("Value not conserved between inputs and outputs.") from tfe
            elif "BadInputsUTxO" in error_json:
                raise BadInputsError("Bad or spent input UTXO detected.") from tfe
            else:
                raise GenericSubmitError("Unhandled submit error occurred.") from tfe

        new_utxos = []
        for i, output in enumerate(final_outputs):
            if output.address == Address.from_primitive(address):
                amounts = {"lovelace": output.amount.coin}
                if output.amount.multi_asset:
                    for policy_id, assets in output.amount.multi_asset.items():
                        for asset_name, qty in assets.items():
                            unit = policy_id + asset_name
                            amounts[unit] = qty
                new_utxos.append({
                    "tx_hash": tx_hash,
                    "tx_index": i,
                    "amounts": amounts
                })

        available_utxos.extend(new_utxos)
        set_utxos_to_cache(address, available_utxos)

        tx.status = "submitted"
        tx.tx_hash = tx_hash
        tx.tx_fee = actual_fee
        tx.tx_size = len(final_tx.to_cbor())
        tx.updated_at = datetime.utcnow()
        session.commit()

    except (ValueNotConservedError, BadInputsError, GenericSubmitError) as e:
        logger.error(f"Transaction {transaction_id} failed due to known submit error: {str(e)}")
        logger.debug(traceback.format_exc())
        if 'tx' in locals():
            tx.status = "failed"
            tx.retries += 1
            tx.error_message = str(e)
            tx.updated_at = datetime.utcnow()
            session.commit()
        if 'wallet' in locals():
            time.sleep(20)
            reload_utxos(wallet.address)

        if tx.retries <= 5:
            logger.info(f"Retrying transaction {transaction_id} (attempt {tx.retries})")
            tx.status = "queued"
            session.commit()
            enqueue_transaction(transaction_id)

    except Exception as e:
        logger.error(f"Transaction {transaction_id} failed: {str(e)}")
        logger.debug(traceback.format_exc())
        if 'tx' in locals():
            tx.status = "failed"
            tx.retries += 1
            tx.error_message = str(e)
            tx.updated_at = datetime.utcnow()
            session.commit()
        if 'wallet' in locals():
            time.sleep(20)
            reload_utxos(wallet.address)

        if tx.retries <= 5:
            logger.info(f"Retrying transaction {transaction_id} (attempt {tx.retries})")
            tx.status = "queued"
            session.commit()
            enqueue_transaction(transaction_id)

    finally:
        session.close()
        logger.info(f"Finished processing transaction {transaction_id}")
        logger.debug(f"UTXO cache size for {address}: {len(get_utxos_from_cache(address)) if 'address' in locals() else 0}")
