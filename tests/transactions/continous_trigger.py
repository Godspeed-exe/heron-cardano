import requests
import random
import time
from uuid import UUID
import sys


API_URL = "http://localhost:8001"
WALLETS_ENDPOINT = f"{API_URL}/wallets/"
TRANSACTIONS_ENDPOINT = f"{API_URL}/transactions/"
NUM_EXECUTIONS = int(sys.argv[1]) if len(sys.argv) > 1 else 10

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
    num_outputs = random.randint(1, 5)
    outputs = []

    for _ in range(num_outputs):
        ada = random.randint(2, 5)
        outputs.append({
            "address": wallet["address"],
            "assets": [
                {
                    "unit": "lovelace",
                    "quantity": str(ada * 1_000_000)
                }
            ]
        })


    # metadata = {
    #     674: {
    #         "msg": "Hello Cardano!"
    #     }
    #     }

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