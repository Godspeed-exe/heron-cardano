from heron_app.workers.worker import celery
from heron_app.db.database import SessionLocal
from heron_app.db.models.transaction import Transaction
from heron_app.db.models.wallet import Wallet
from heron_app.utils.redis_client import redis_client

from blockfrost import BlockFrostApi, ApiUrls
from pycardano import (
    crypto, ExtendedSigningKey, TransactionInput, TransactionOutput, TransactionBody,
    TransactionWitnessSet, VerificationKeyWitness, fee, Value,
    Transaction as CardanoTransaction, Address, BlockFrostChainContext
)
from cryptography.fernet import Fernet

import os
import json
import logging
import traceback
from datetime import datetime
import redis_lock


# Logging setup
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")
handler.setFormatter(formatter)
if not logger.hasHandlers():
    logger.addHandler(handler)

# Helper functions for UTXO Redis cache
def get_utxo_cache_key(address):
    return f"utxos:{address}"

def get_utxos_from_cache(address):
    key = get_utxo_cache_key(address)
    data = redis_client.get(key)
    if data:
        return json.loads(data)
    return []

def set_utxos_to_cache(address, utxo_list):
    key = get_utxo_cache_key(address)
    redis_client.set(key, json.dumps(utxo_list), ex=300)  # 5 min expiry

def reload_utxos(address):
    network = os.getenv("network", "mainnet")
    base_url = ApiUrls.preprod.value if network == "testnet" else ApiUrls.mainnet.value
    api = BlockFrostApi(project_id=os.getenv("BLOCKFROST_PROJECT_ID"), base_url=base_url)

    logger.info(f"Reloading UTXOs from Blockfrost for {address}")
    raw_utxos = api.address_utxos(address)

    result = []
    for utxo in raw_utxos:
        for amt in utxo.amount:
            if amt.unit == "lovelace":
                result.append({
                    "tx_hash": utxo.tx_hash,
                    "tx_index": utxo.tx_index,
                    "amount": int(amt.quantity)
                })
                break

    set_utxos_to_cache(address, result)
    logger.info(f"Cached {len(result)} UTXOs for {address}")

@celery.task(name="heron_app.workers.tasks.process_transaction")
def process_transaction(transaction_id):
    session = SessionLocal()
    logger.info(f"Started processing transaction {transaction_id}")

    try:
        tx = session.query(Transaction).filter(Transaction.id == transaction_id).first()
        if not tx:
            logger.warning(f"Transaction {transaction_id} not found.")
            return

        wallet = session.query(Wallet).filter(Wallet.id == tx.wallet_id).first()
        if not wallet:
            logger.error(f"Wallet {tx.wallet_id} not found.")
            tx.status = "failed"
            session.commit()
            return

        address = wallet.address
        logger.info(f"Using wallet address: {address}")
        lock_key = f"utxo-lock:{address}"

        with redis_lock.Lock(redis_client, lock_key, expire=30, auto_renewal=True):
            available_utxos = get_utxos_from_cache(address)
            if not available_utxos:
                reload_utxos(address)
                available_utxos = get_utxos_from_cache(address)

            if not available_utxos:
                logger.error("No UTXOs available")
                tx.status = "failed"
                session.commit()
                return

            # Decrypt and derive keys
            fernet = Fernet(os.getenv("WALLET_ENCRYPTION_KEY"))
            mnemonic = fernet.decrypt(wallet.encrypted_root_key.encode()).decode()
            root_key = crypto.bip32.HDWallet.from_mnemonic(mnemonic)
            payment_key = root_key.derive_from_path("m/1852'/1815'/0'/0/0")
            payment_skey = ExtendedSigningKey.from_hdwallet(payment_key)

            # Setup context
            network = os.getenv("network", "mainnet")
            context = BlockFrostChainContext(
                project_id=os.getenv("BLOCKFROST_PROJECT_ID"),
                base_url=ApiUrls.preprod.value if network == "testnet" else ApiUrls.mainnet.value,
            )

            # STEP 1: Select UTXOs
            input_utxos = []
            total_input = 0
            DUMMY_FEE = 200_000
            amount_needed = tx.amount_lovelace + DUMMY_FEE

            while total_input < amount_needed and available_utxos:
                utxo = available_utxos.pop(0)
                tx_input = TransactionInput.from_primitive([utxo['tx_hash'], utxo['tx_index']])
                input_utxos.append(tx_input)
                total_input += utxo['amount']

            if total_input < amount_needed:
                logger.error("Not enough ADA to cover transaction and dummy fee.")
                tx.status = "failed"
                session.commit()
                return

            # STEP 2: Draft transaction with dummy fee
            receiver_output = TransactionOutput(Address.from_primitive(tx.to_address), tx.amount_lovelace)
            change_output = TransactionOutput(Address.from_primitive(address), total_input - tx.amount_lovelace - DUMMY_FEE)
            provisional_body = TransactionBody(inputs=input_utxos, outputs=[receiver_output, change_output], fee=DUMMY_FEE)
            signature = payment_skey.sign(provisional_body.hash())
            witness_set = TransactionWitnessSet(vkey_witnesses=[
                VerificationKeyWitness(payment_skey.to_verification_key(), signature)
            ])
            draft_tx = CardanoTransaction(provisional_body, witness_set)

            # STEP 3: Estimate actual fee
            actual_fee = fee(context, len(draft_tx.to_cbor()))
            logger.info(f"Estimated fee: {actual_fee}")

            # STEP 4: Final transaction build
            final_change = total_input - tx.amount_lovelace - actual_fee
            if final_change < 0:
                logger.error("Not enough ADA to cover actual fee.")
                tx.status = "failed"
                session.commit()
                return

            outputs = [receiver_output]
            if final_change > 0:
                outputs.append(TransactionOutput(Address.from_primitive(address), final_change))

            final_body = TransactionBody(inputs=input_utxos, outputs=outputs, fee=actual_fee)
            final_signature = payment_skey.sign(final_body.hash())
            final_witness = TransactionWitnessSet(vkey_witnesses=[
                VerificationKeyWitness(payment_skey.to_verification_key(), final_signature)
            ])
            final_tx = CardanoTransaction(final_body, final_witness)

            # STEP 5: Submit
            tx_hash = context.submit_tx(final_tx.to_cbor())
            tx.status = "submitted"
            tx.tx_hash = tx_hash
            tx.tx_fee = actual_fee
            tx.tx_size = len(final_tx.to_cbor())
            tx.updated_at = datetime.utcnow()
            session.commit()

            logger.info(f"Transaction {tx.id} submitted successfully: {tx_hash}")

            # STEP 6: Update UTXO cache with change
            if final_change > 0:
                available_utxos.append({
                    "tx_hash": tx_hash,
                    "tx_index": 1 if len(outputs) > 1 else 0,
                    "amount": final_change
                })
            set_utxos_to_cache(address, available_utxos)

    except Exception as e:
        logger.error(f"Transaction {transaction_id} failed: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        if 'tx' in locals():
            tx.status = "failed"
            tx.error_message = str(e)
            tx.updated_at = datetime.utcnow()
            session.commit()
        if 'wallet' in locals():
            reload_utxos(wallet.address)

    finally:
        session.close()
        logger.info(f"Finished processing transaction {transaction_id}")
        logger.info(f"UTXO cache size for {address}: {len(get_utxos_from_cache(address))}")