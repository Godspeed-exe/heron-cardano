import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException  # type: ignore
from blockfrost import BlockFrostApi, ApiError, ApiUrls, BlockFrostIPFS
from pycardano import (
    Address,
    PaymentKeyPair,
    PaymentSigningKey,
    PaymentVerificationKey,
    ScriptAll,
    ScriptPubkey,
    InvalidHereAfter,
)

SLOTS_PER_SECOND = 1  # Preprod is 1 slot/sec
NETWORK_START = datetime(2020, 7, 29, tzinfo=timezone.utc)  # Shelley start


BLOCKFROST_API_KEY = os.getenv("BLOCKFROST_PROJECT_ID")

if not BLOCKFROST_API_KEY:
    # Fail fast with a clear error if configuration is missing
    raise RuntimeError("BLOCKFROST_PROJECT_ID environment variable is not set.")

if len(BLOCKFROST_API_KEY) < 7:
    raise RuntimeError("BLOCKFROST_PROJECT_ID value is invalid or too short.")

network = BLOCKFROST_API_KEY[:7].lower()

network_map = {
    "preprod": ApiUrls.preprod.value,
    "preview": ApiUrls.preview.value,
    "mainnet": ApiUrls.mainnet.value,
}

if network not in network_map and os.getenv("CUSTOM_BLOCKFROST_API_URL") is None:
    raise RuntimeError(
        "Unsupported network derived from BLOCKFROST_PROJECT_ID. "
        "Set CUSTOM_BLOCKFROST_API_URL for custom networks."
    )

BASE_URL = network_map.get(network, os.getenv("CUSTOM_BLOCKFROST_API_URL"))


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

network = os.getenv("network")


def _get_blockfrost_api() -> BlockFrostApi:
    """
    Centralized Blockfrost API client construction with validated configuration.
    """
    return BlockFrostApi(project_id=BLOCKFROST_API_KEY, base_url=BASE_URL)


def _validate_address(address: str) -> None:
    """
    Basic internal validation to avoid unnecessary Blockfrost calls for obviously
    invalid addresses.
    """
    if not address:
        raise HTTPException(status_code=400, detail="Address must not be empty.")

    try:
        # This will raise if the address is malformed
        Address.from_primitive(address)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Cardano address format.")


def get_balance(address: str) -> dict:
    """
    Return balance for a given address by aggregating all UTXOs.
    Performs internal address validation before querying Blockfrost.
    """

    _validate_address(address)
    api = _get_blockfrost_api()

    try:
        # Use explicit pagination to minimise repeated calls from higher layers.
        # This fetches all pages once per call and aggregates locally.
        page = 1
        total_lovelace = 0
        asset_totals: dict = {}

        while True:
            utxos = api.address_utxos(address=address, count=100, page=page)
            if not utxos:
                break

            for utxo in utxos:
                for amt in utxo.amount:
                    if amt.unit == "lovelace":
                        total_lovelace += int(amt.quantity)
                    else:
                        if amt.unit not in asset_totals:
                            asset_totals[amt.unit] = 0
                        asset_totals[amt.unit] += int(amt.quantity)

            if len(utxos) < 100:
                break

            page += 1

        return {
            "lovelace": str(total_lovelace),
            "assets": {k: str(v) for k, v in asset_totals.items()},
        }

    except ApiError as e:
        # 404: Treat as "no balance yet" instead of hard error.
        if e.status_code == 404:
            return {"lovelace": "0", "assets": {}}

        # Authentication / quota issues – surface a clear, firm error.
        if e.status_code in (401, 403, 429):
            raise HTTPException(
                status_code=502,
                detail=f"Blockfrost API authentication or rate-limit error: {e}",
            )

        # Fallback – still differentiate as upstream issue.
        raise HTTPException(status_code=502, detail=f"Blockfrost API error: {e}")


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