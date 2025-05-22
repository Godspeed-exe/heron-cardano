import os
import psycopg2
import requests
from jinja2 import Template

# Configuration
DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/postgres")
BLOCKFROST_KEY = os.getenv("BLOCKFROST_PROJECT_ID")
cardano_network = os.getenv("network", "testnet")
NETWORK = "preprod" if cardano_network == "testnet" else "mainnet"  
OURA_TEMPLATE_PATH = "/app/oura/config-template.toml"
OURA_CONFIG_PATH = "/app/oura/config.toml"


def get_pending_transaction_hash():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("""
        SELECT tx_hash FROM transactions
        WHERE status = 'submitted'
        ORDER BY created_at ASC LIMIT 1
    """)
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else None


def fetch_earlier_block_point(tx_hash, steps_back=10):
    headers = {"project_id": BLOCKFROST_KEY}

    # Step 1: Get the block hash for the transaction
    tx_url = f"https://cardano-{NETWORK}.blockfrost.io/api/v0/txs/{tx_hash}"
    tx_response = requests.get(tx_url, headers=headers)
    if tx_response.status_code != 200:
        raise Exception(f"❌ Failed to fetch tx info from Blockfrost: {tx_response.text}")
    block_hash = tx_response.json()["block"]

    # Step 2: Walk back N blocks
    current_hash = block_hash
    for _ in range(steps_back):
        block_url = f"https://cardano-{NETWORK}.blockfrost.io/api/v0/blocks/{current_hash}"
        block_response = requests.get(block_url, headers=headers)
        if block_response.status_code != 200:
            raise Exception(f"❌ Failed to fetch block info: {block_response.text}")
        block_data = block_response.json()
        if not block_data.get("previous_block"):
            break  # We reached genesis
        current_hash = block_data["previous_block"]

    # Step 3: Get slot of final block
    final_block_url = f"https://cardano-{NETWORK}.blockfrost.io/api/v0/blocks/{current_hash}"
    final_response = requests.get(final_block_url, headers=headers)
    if final_response.status_code != 200:
        raise Exception(f"❌ Failed to fetch final block info: {final_response.text}")
    final_data = final_response.json()
    return final_data["slot"], current_hash


def render_oura_config(starting_point_type, slot=None, block_hash=None):
    with open(OURA_TEMPLATE_PATH, "r") as f:
        template = Template(f.read())

    rendered = template.render(
        starting_point_type=starting_point_type,
        slot=slot,
        block_hash=block_hash
    )

    with open(OURA_CONFIG_PATH, "w") as f:
        f.write(rendered)
    print(f"✅ Oura config written with start: {starting_point_type} {slot or ''} {block_hash or ''}")


def main():
    tx_hash = get_pending_transaction_hash()

    if tx_hash:
        print(f"🔍 Found pending tx: {tx_hash}")
        slot, block_hash = fetch_earlier_block_point(tx_hash, steps_back=10)

        if os.path.exists("/app/oura/cursor"):
            os.remove("/app/oura/cursor")
            print("🗑️ Removed /cursor file")
        print(f"📦 Using Point: [ {slot}, \"{block_hash}\" ]")
        render_oura_config("Point", slot, block_hash)
    else:
        print("🟢 No pending txs found. Starting from Tip.")
        render_oura_config("Tip")


if __name__ == "__main__":
    print(f"🔧 DB URL: {DB_URL}")
    print(f"🌐 Blockfrost Project ID: {BLOCKFROST_KEY}")
    print(f"🌐 Cardano network: {cardano_network}")
    main()