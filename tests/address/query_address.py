from pycardano import *

from blockfrost import BlockFrostApi, ApiUrls
import os
from dotenv import load_dotenv
load_dotenv()

ADDRESS="addr_test1qphe4ktmglgyhwqh42ltf8y2nxxgqvdv6c8tcgp7d637xqwsy7cw3eq0wqtup2fyh54q3e0r0ulvjhd6aewm2l6y7k9q7952rc"


#query address from blockfrost


api_key = os.getenv("BLOCKFROST_PROJECT_ID")
network = os.getenv("network")
base_url = ApiUrls.preprod.value if network == "testnet" else ApiUrls.mainnet.value

api = BlockFrostApi(project_id=api_key, base_url=base_url)

#query utoxs for this address



page = 1
all_utxos = []

while True:
    raw_utxos = api.address_utxos(address=ADDRESS, count=100, page=page)
    if not raw_utxos:
        break

    for utxo in raw_utxos:
        if utxo.data_hash is not None and utxo.inline_datum is not None:
            print(utxo)
            print("---------------------------------")

    if len(raw_utxos) < 100:
        break  # No more pages
    page += 1







# for utxo in response:
#     if utxo.data_hash is not None:
#         print(utxo)
#         print("---------------------------------")
# # print(response)




