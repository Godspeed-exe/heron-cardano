from fastapi import FastAPI # type: ignore
from heron_app.api.routes import router as api_router
from heron_app.db.database import SessionLocal
from heron_app.db.models.transaction import Transaction
from heron_app.workers.tasks import process_transaction, enqueue_transaction
from heron_app.db.models.wallet import Wallet
from heron_app.workers.start_wallet_worker import start_worker
from heron_app.utils.registry_loader import start_registry_loader

import time
import os


app = FastAPI()
app.include_router(api_router)

@app.on_event("startup")
def requeue_pending_transactions():

    BLOCKFROST_PROJECT_ID = os.getenv("BLOCKFROST_PROJECT_ID")
    POSTGRES_USER = os.getenv("POSTGRES_USER")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
    WALLET_ENCRYPTION_KEY = os.getenv("WALLET_ENCRYPTION_KEY")

    print(f"BLOCKFROST_PROJECT_ID: {BLOCKFROST_PROJECT_ID}")
    print(f"POSTGRES_USER: {POSTGRES_USER}")
    print(f"POSTGRES_PASSWORD: {POSTGRES_PASSWORD}")    
    print(f"WALLET_ENCRYPTION_KEY: {WALLET_ENCRYPTION_KEY}")

    if BLOCKFROST_PROJECT_ID == "preproddummy" and POSTGRES_USER == "dummy" and POSTGRES_PASSWORD == "dummy" and WALLET_ENCRYPTION_KEY == "dummy":
        print("Running in CI environment...")

    else:
        print("Running in PROD environment...")
        session = SessionLocal()
        try:

            start_registry_loader()

            wallets = session.query(Wallet).all()
            for wallet in wallets:
                start_worker(str(wallet.id))

            time.sleep(2)  # Wait for workers to start

            pending_txs = session.query(Transaction).filter_by(status="queued").all()
            for tx in pending_txs:
                print(f"Requeuing transaction {tx.id}")
                enqueue_transaction(str(tx.id))  # Send to Celery
        finally:
            session.close()