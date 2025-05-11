import os
from fastapi import HTTPException
from blockfrost import BlockFrostApi, ApiError, ApiUrls,BlockFrostIPFS
from heron_app.core.config import settings
from heron_app.schemas.wallet import WalletOut
from pycardano import *
import os


network = os.getenv('network')

def get_balance(address: str) -> dict:
    api_key = os.getenv("BLOCKFROST_PROJECT_ID")
    network = os.getenv("network")
    base_url = ApiUrls.preprod.value if network == "testnet" else ApiUrls.mainnet.value

    api = BlockFrostApi(project_id=api_key, base_url=base_url)

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