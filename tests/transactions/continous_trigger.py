import requests
import random
import time
from uuid import UUID

API_URL = "http://localhost:8001"
WALLETS_ENDPOINT = f"{API_URL}/wallets"
TRANSACTIONS_ENDPOINT = f"{API_URL}/transactions"
NUM_EXECUTIONS = 10000


def load_wallet():
    response = requests.get(WALLETS_ENDPOINT)
    response.raise_for_status()
    wallets = response.json()
    if not wallets:
        raise Exception("No wallets found")
    return wallets[0]  # Use the first wallet

def generate_transaction_payload(wallet):
    num_outputs = random.randint(1, 30)
    outputs = []

    for _ in range(num_outputs):
        ada = random.randint(2, 10)
        outputs.append({
            "address": wallet["address"],
            "assets": [
                {
                    "unit": "lovelace",
                    "quantity": str(ada * 1_000_000)
                }
            ]
        })

    return {
        "wallet_id": wallet["id"],
        "outputs": outputs,
        "metadata": None
    }

def main():
    wallet = load_wallet()
    print(f"Using wallet: {wallet['name']} ({wallet['id']})")

    for i in range(NUM_EXECUTIONS):
        payload = generate_transaction_payload(wallet)
        response = requests.post(TRANSACTIONS_ENDPOINT, json=payload)
        if response.status_code == 200:
            print(f"[{i+1}/{NUM_EXECUTIONS}] Transaction submitted: {response.json()['id']}")
        else:
            print(f"[{i+1}/{NUM_EXECUTIONS}] Failed: {response.status_code} - {response.text}")
        # time.sleep(0.1)  # Optional: throttle requests

if __name__ == "__main__":
    main()