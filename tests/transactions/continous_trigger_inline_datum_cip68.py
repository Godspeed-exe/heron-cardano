import requests
import random
import time
from uuid import UUID

API_URL = "http://localhost:8001"
WALLETS_ENDPOINT = f"{API_URL}/wallets/"
TRANSACTIONS_ENDPOINT = f"{API_URL}/transactions/"
NUM_EXECUTIONS = 1


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
    num_outputs = 1
    outputs = []

    inline_datum = {
        "name": "NerdsWifLambo",
        "description": "Lambo's for everyone",
        "ticker": "NwifLAMBO",
        "decimals": 6,
        "url": "https://x.com",
        "logo": "ipfs://QmbpeH5MdqYjFvrqNAG6o3AgU9hP2QrBukBc4XvaALiZT5",
        "image": "ipfs://QmbpeH5MdqYjFvrqNAG6o3AgU9hP2QrBukBc4XvaALiZT5",
        "version": 2
    }

    # inline_datum = {
    #     "type": "my inline datum",
    #     "extra": {
    #         "name": "datum name",
    #         "description": "datum description"
    #     }
    # }


    for _ in range(num_outputs):
        ada = random.randint(2, 3)
        outputs.append({
            "address": wallet["address"],
            "assets": [
                {
                    "unit": "lovelace",
                    "quantity": str(ada * 1_000_000)
                }
            ],
            "datum": inline_datum
        })




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