from fastapi import FastAPI
from heron_app.api.routes import router as api_router
from heron_app.db.database import SessionLocal
from heron_app.db.models.transaction import Transaction
from heron_app.workers.tasks import process_transaction

app = FastAPI()
app.include_router(api_router)

@app.on_event("startup")
def requeue_pending_transactions():
    session = SessionLocal()
    try:
        pending_txs = session.query(Transaction).filter_by(status="queued").all()
        for tx in pending_txs:
            print(f"Requeuing transaction {tx.id}")
            process_transaction.delay(str(tx.id))  # Send to Celery
    finally:
        session.close()