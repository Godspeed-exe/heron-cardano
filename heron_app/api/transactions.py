from fastapi import APIRouter, HTTPException, Path
from heron_app.schemas.transaction import TransactionCreate, TransactionOut
from heron_app.db.models.transaction import Transaction
from heron_app.db.models.wallet import Wallet
from heron_app.db.database import SessionLocal
from heron_app.workers.tasks import process_transaction

from uuid import uuid4
from datetime import datetime

router = APIRouter()

@router.post("/", response_model=TransactionOut)
def submit_transaction(tx: TransactionCreate):
    session = SessionLocal()
    try:
        # Check if the wallet_id exists
        wallet = session.query(Wallet).filter(Wallet.id == tx.wallet_id).first()
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")

        # Create transaction record
        tx_record = Transaction(
            id=uuid4(),
            wallet_id=tx.wallet_id,
            to_address=tx.to_address,
            amount_lovelace=tx.amount_lovelace,
            metadata_json=tx.metadata,
            status="queued",
            created_at=datetime.utcnow()
        )
        session.add(tx_record)
        session.commit()
        session.refresh(tx_record)

        process_transaction.delay(str(tx_record.id))

        return tx_record

    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/{transaction_id}", response_model=TransactionOut)
def get_transaction(transaction_id: str = Path(..., description="UUID of the transaction")):
    session = SessionLocal()
    try:
        transaction = session.query(Transaction).filter(Transaction.id == transaction_id).first()
        if not transaction:
            raise HTTPException(status_code=404, detail="Transaction not found")
        return transaction
    finally:
        session.close()