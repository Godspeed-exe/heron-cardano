from fastapi import APIRouter, HTTPException, Path  # type: ignore
from sqlalchemy.orm import joinedload # type: ignore
from heron_app.schemas.transaction import TransactionCreate, TransactionOut
from heron_app.db.models.transaction import Transaction
from heron_app.db.models.wallet import Wallet
from heron_app.db.models.transaction_output import TransactionOutput
from heron_app.db.models.transaction_output_asset import TransactionOutputAsset
from heron_app.db.database import SessionLocal
from heron_app.workers.tasks import process_transaction

from uuid import uuid4
from datetime import datetime

router = APIRouter()


@router.post("/", response_model=TransactionOut)
def submit_transaction(tx: TransactionCreate):
    session = SessionLocal()
    try:
        wallet = session.query(Wallet).filter(Wallet.id == tx.wallet_id).first()
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")

        # Create base transaction record
        tx_record = Transaction(
            id=uuid4(),
            wallet_id=tx.wallet_id,
            metadata_json=tx.metadata,
            status="queued",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(tx_record)
        session.flush()  # Get numeric_id

        for output_data in tx.outputs:
            output = TransactionOutput(
                transaction_id=tx_record.numeric_id,
                address=output_data.address,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(output)
            session.flush()  # Get output.id

            for asset in output_data.assets:
                asset_row = TransactionOutputAsset(
                    output_id=output.id,
                    unit=asset.unit,
                    quantity=asset.quantity,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                session.add(asset_row)

        session.commit()

        # Re-fetch transaction with related outputs/assets before session closes
        db_tx = (
            session.query(Transaction)
            .options(joinedload(Transaction.outputs).joinedload(TransactionOutput.assets))
            .filter(Transaction.id == tx_record.id)
            .first()
        )

        # Trigger async task
        process_transaction.delay(str(tx_record.id))

        return db_tx

    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/{transaction_id}", response_model=TransactionOut)
def get_transaction(transaction_id: str = Path(..., description="UUID of the transaction")):
    session = SessionLocal()
    try:
        transaction = (
            session.query(Transaction)
            .options(joinedload(Transaction.outputs).joinedload(TransactionOutput.assets))
            .filter(Transaction.id == transaction_id)
            .first()
        )
        if not transaction:
            raise HTTPException(status_code=404, detail="Transaction not found")
        return transaction
    finally:
        session.close()