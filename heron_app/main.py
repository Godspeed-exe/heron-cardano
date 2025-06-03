from fastapi import FastAPI # type: ignore
from heron_app.api.routes import router as api_router
from heron_app.db.database import SessionLocal
from heron_app.db.models.transaction import Transaction
from heron_app.workers.tasks import process_transaction, enqueue_transaction
from heron_app.db.models.wallet import Wallet
from heron_app.workers.start_wallet_worker import start_worker
from heron_app.utils.registry_loader import start_registry_loader

import time

app = FastAPI()
app.include_router(api_router)

@app.on_event("startup")
def requeue_pending_transactions():
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