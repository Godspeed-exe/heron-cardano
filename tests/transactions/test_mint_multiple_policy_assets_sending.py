import requests
import random
import time
from uuid import UUID

API_URL = "http://localhost:8001"
WALLETS_ENDPOINT = f"{API_URL}/wallets/"
POLICY_ENDPOINT = f"{API_URL}/policies/"
TRANSACTIONS_ENDPOINT = f"{API_URL}/transactions/"
NUM_EXECUTIONS = 1

ASSET= "CHARACTER"
NUM_ASSETS = 3


def load_wallet():
    response = requests.get(WALLETS_ENDPOINT)
    response.raise_for_status()
    wallets = response.json()
    if not wallets:
        raise Exception("No wallets found")
    
    #select a random wallet
    wallet = random.choice(wallets)
    if not wallet:
        raise Exception("No wallets found")
    
    return wallet 

def generate_transaction_payload(wallet):


    response = requests.get(POLICY_ENDPOINT)
    response.raise_for_status()
    policies = response.json()
    if not policies:
        raise Exception("No policies found")
    

    
    outputs = []



    mints = []

    for _ in range(NUM_ASSETS):
        policy = random.choice(policies)

        for i in range(1, 5):
            mints.append({
                "policy_id": policy["policy_id"],
                "asset_name": f"{ASSET}{i:04d}",
                "quantity": str(random.randint(1, 10) * 1_000_000)
            })


    copy_mints = mints.copy()

    outputs = []

    while len(copy_mints) > 0:

        print(f"mints to begin with: {copy_mints}")
        asset = random.choice(copy_mints)
        num_outputs = random.randint(1, 3)


        for _ in range(num_outputs):

            if int(asset['quantity']) > 1_000_000:
                asset_quantity = random.randint(1_000_000, int(asset['quantity']))

            outputs.append({
                "address": wallet["address"],
                "assets": [
                    {
                        "unit": f"{asset['policy_id']}{asset['asset_name'].encode('utf-8').hex()}",
                        "quantity": str(asset_quantity)
                    }
                ]
            })

        asset['quantity'] = str(int(asset['quantity']) - asset_quantity)
        
        for m in copy_mints:
            if int(m['quantity']) <= 1_000_000:
                copy_mints.remove(m)

        print(f"Mints left: {copy_mints}")




    return {
        "wallet_id": wallet["id"],
        "outputs": outputs,
        "mint": mints
    }

def main():


    for i in range(NUM_EXECUTIONS):

        wallet = load_wallet()
        print(f"Using wallet: {wallet['name']} ({wallet['id']})")

        payload = generate_transaction_payload(wallet)
        response = requests.post(TRANSACTIONS_ENDPOINT, json=payload)
        if response.status_code == 200:
            print(f"[{i+1}/{NUM_EXECUTIONS}] Transaction submitted: {response.json()['id']} - {wallet['name']}")
        else:
            print(f"[{i+1}/{NUM_EXECUTIONS}] Failed: {response.status_code} - {response.text}")
        # time.sleep(0.1)  # Optional: throttle requests

if __name__ == "__main__":
    main()