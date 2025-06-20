import os
from fastapi import HTTPException # type: ignore
from blockfrost import BlockFrostApi, ApiError, ApiUrls,BlockFrostIPFS
from heron_app.core.config import settings
from heron_app.schemas.wallet import WalletOut
from pycardano import (
    PaymentKeyPair,
    PaymentSigningKey,
    PaymentVerificationKey,
    ScriptAll,
    ScriptPubkey,
    InvalidHereAfter,
)
from datetime import datetime, timezone
from typing import Optional

import os

SLOTS_PER_SECOND = 1  # Preprod is 1 slot/sec
NETWORK_START = datetime(2020, 7, 29, tzinfo=timezone.utc)  # Shelley start

BLOCKFROST_API_KEY = os.getenv("BLOCKFROST_PROJECT_ID")
network =  BLOCKFROST_API_KEY[:7].lower()
BASE_URL = ApiUrls.preprod.value if network == "preprod" else ApiUrls.preview.value if network == "preview" else ApiUrls.mainnet.value


def utc_to_slot(dt: datetime) -> int:
    delta = dt - NETWORK_START
    return int(delta.total_seconds() * SLOTS_PER_SECOND)

class TransactionSubmitError(Exception):
    """Base class for transaction submit errors"""
    pass

class ValueNotConservedError(TransactionSubmitError):
    """Raised when the input/output values don't match"""
    pass

class BadInputsError(TransactionSubmitError):
    """Raised when UTXOs used as inputs are invalid or already spent"""
    pass

class GenericSubmitError(TransactionSubmitError):
    """Fallback for other transaction submit errors"""
    pass

network = os.getenv('network')

def get_balance(address: str) -> dict:


    api = BlockFrostApi(project_id=BLOCKFROST_API_KEY, base_url=BASE_URL)

    try:
        utxos = api.address_utxos(address)

        total_lovelace = 0
        asset_totals = {}

        for utxo in utxos:
            for amt in utxo.amount:
                if amt.unit == "lovelace":
                    total_lovelace += int(amt.quantity)
                else:
                    if amt.unit not in asset_totals:
                        asset_totals[amt.unit] = 0
                    asset_totals[amt.unit] += int(amt.quantity)

        return {
            "lovelace": str(total_lovelace),
            "assets": {k: str(v) for k, v in asset_totals.items()}
        }

    except ApiError as e:
        if e.status_code == 404:
            return {"lovelace": "0", "assets": {}}        
        raise HTTPException(status_code=500, detail=f"Blockfrost API error: {e}")
    

def generate_policy(lock_date: Optional[datetime] = None):
    # 1. Generate key pair
    key_pair = PaymentKeyPair.generate()
    skey = key_pair.signing_key
    vkey = key_pair.verification_key

    # 2. Create script components
    pubkey_script = ScriptPubkey(vkey.hash())
    scripts = [pubkey_script]

    locking_slot = None
    if lock_date:
        locking_slot = utc_to_slot(lock_date)
        scripts.append(InvalidHereAfter(locking_slot))

    policy = ScriptAll(scripts)
    policy_id = policy.hash().payload.hex()



    return policy_id, skey.to_cbor_hex(), locking_slot