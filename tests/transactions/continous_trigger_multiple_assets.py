import requests
import random
import time
from uuid import UUID

API_URL = "http://localhost:8001"
WALLETS_ENDPOINT = f"{API_URL}/wallets/"
TRANSACTIONS_ENDPOINT = f"{API_URL}/transactions/"
NUM_EXECUTIONS = 200
UNITS=[
    "63f9a5fc96d4f87026e97af4569975016b50eef092a46859b61898e50014df104c51", #LQ
    "63f9a5fc96d4f87026e97af4569975016b50eef092a46859b61898e50014df10494e4459", #INDY
    "63f9a5fc96d4f87026e97af4569975016b50eef092a46859b61898e50014df104d494c4b", #MILK
    "bfcf49670366e15d7236d0a775bc764d61cb97b4c1f70e730c4eb6d45a4f4f" #ZOO
    ]


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
    num_outputs = random.randint(1, 3)
    outputs = []

    for _ in range(num_outputs):
        ada = random.randint(0, 2)
        
        number_of_assets = random.randint(1, len(UNITS))

        payload = {
            "address": wallet["address"],
            "assets": [
                {
                    "unit": "lovelace",
                    "quantity": str(ada * 1_000_000)
                }
            ]
        }

        for insert_asset in range(number_of_assets):
            unit = random.choice(UNITS)
            asset = random.randint(1, 20)

            payload["assets"].append({
                "unit": f"{unit}",
                "quantity": str(asset * 100_000)
            })

        outputs.append(payload)
        


    return {
        "wallet_id": wallet["id"],
        "outputs": outputs
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