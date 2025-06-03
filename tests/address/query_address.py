from pycardano import *

from blockfrost import BlockFrostApi, ApiUrls
import os


ADDRESS="addr_test1qphe4ktmglgyhwqh42ltf8y2nxxgqvdv6c8tcgp7d637xqwsy7cw3eq0wqtup2fyh54q3e0r0ulvjhd6aewm2l6y7k9q7952rc"


#query address from blockfrost


api_key = os.getenv("BLOCKFROST_PROJECT_ID")
network = os.getenv("network")
base_url = ApiUrls.preprod.value if network == "testnet" else ApiUrls.mainnet.value

api = BlockFrostApi(project_id=api_key, base_url=base_url)

#query utoxs for this address






response = api.address_utxos(ADDRESS)
print(response)




