from fastapi import APIRouter, HTTPException, Path  # type: ignore
from sqlalchemy.orm import joinedload # type: ignore
from heron_app.schemas.transaction import TransactionCreate, TransactionOut
from heron_app.db.models.transaction import Transaction
from heron_app.db.models.wallet import Wallet
from heron_app.db.models.transaction_output import TransactionOutput
from heron_app.db.models.transaction_output_asset import TransactionOutputAsset
from heron_app.db.models.transaction_mint import TransactionMint
from heron_app.db.models.minting_policies import MintingPolicy  # noqa: F401
from heron_app.db.database import SessionLocal
from heron_app.workers.tasks import process_transaction, enqueue_transaction
from heron_app.utils.registry_loader import get_registry_labels

from uuid import uuid4
from datetime import datetime


router = APIRouter()



@router.post("/",
                summary="Submit a new transaction",
                description="Submits a new transaction to the Heron API. The transaction includes metadata, outputs, and optional minting information. The transaction is queued for processing.",
                responses={
                    200: {
                        "description": "Transaction submitted successfully",
                        "content": {
                            "application/json": {
                                "example": {
                                    "id": "uuid",
                                    "wallet_id": "uuid",
                                    "metadata_json": {"1": "value"},
                                    "status": "queued",
                                    "created_at": "2023-10-01T00:00:00Z",
                                    "updated_at": "2023-10-01T00:00:00Z",
                                    "outputs": [
                                        {
                                            "address": "addr_test1...",
                                            "datum": None,
                                            "assets": [
                                                {"unit": "asset1", "quantity": 1000}
                                            ]
                                        }
                                    ],
                                    "mint": []
                                }
                            }
                        }
                    },  
                    400: {
                        "description": "Bad request",
                        "content": {
                            "application/json": {
                                "example": {
                                    "detail": "Error message"
                                }
                            }
                        }
                    },
                    404: {
                        "description": "Wallet not found",
                        "content": {
                            "application/json": {
                                "example": {
                                    "detail": "Wallet not found"
                                }
                            }
                        }
                    },
                    422: {
                        "description": "Validation error",
                        "content": {
                            "application/json": {
                                "example": {
                                    "detail": "Validation error message"
                                }
                            }
                        }
                    },
                    500: {
                        "description": "Internal server error",
                        "content": {
                            "application/json": {
                                "example": {
                                    "detail": "Error message"
                                }
                            }
                        }
                    }
                },
                response_model=TransactionOut
              )
def submit_transaction(tx: TransactionCreate):
    session = SessionLocal()
    try:
        wallet = session.query(Wallet).filter(Wallet.id == tx.wallet_id).first()
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")
        


        metadata_with_int_keys = None

        # Inside your endpoint
        if tx.metadata is not None:
            if not isinstance(tx.metadata, dict):
                raise HTTPException(status_code=400, detail="Metadata must be a dictionary")
            

            valid_labels = get_registry_labels()

            invalid_labels = []
            for key in tx.metadata.keys():
                try:
                    int_key = int(key)
                except ValueError:
                    raise HTTPException(status_code=400, detail=f"Metadata key '{key}' is not a valid integer")
                
                if int_key not in valid_labels:
                    invalid_labels.append(int_key)

            if invalid_labels:
                raise HTTPException(
                    status_code=400,
                    detail=f"The following metadata labels are not registered in CIP-0010: {invalid_labels}"
                )


            metadata_with_int_keys = {int(k): v for k, v in tx.metadata.items()}


        # Create base transaction record
        tx_record = Transaction(
            id=uuid4(),
            wallet_id=tx.wallet_id,
            metadata_json=metadata_with_int_keys,
            status="queued",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(tx_record)
        session.flush()  # Get numeric_id

        for output_data in tx.outputs:

            inline_datum = None
            if hasattr(output_data, 'datum') and output_data.datum is not None:
                if not isinstance(output_data.datum, dict):
                    raise HTTPException(status_code=400, detail="Datum must be a dictionary")
                
                inline_datum = output_data.datum

            output = TransactionOutput(
                transaction_id=tx_record.numeric_id,
                address=output_data.address,
                datum=inline_datum,  # Inline datum can be None
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


        # Handle minting if provided
        if tx.mint:
            for mint in tx.mint:

                mint_policy = session.query(MintingPolicy).filter(MintingPolicy.policy_id == mint.policy_id).first()

                if not mint_policy:
                    raise HTTPException(status_code=400, detail="Minting Policy not found on your instance.")

                mint_record = TransactionMint(
                    transaction_id=tx_record.numeric_id,
                    policy_id=mint.policy_id,
                    asset_name=mint.asset_name,
                    quantity=mint.quantity,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                session.add(mint_record)

        session.commit()

        # Re-fetch transaction with related outputs/assets before session closes
        db_tx = (
            session.query(Transaction)
            .options(joinedload(Transaction.outputs).joinedload(TransactionOutput.assets))
            .filter(Transaction.id == tx_record.id)
            .first()
        )

        # Trigger async task
        queue_name = f"wallet_{tx_record.wallet_id}"
        process_transaction.apply_async(args=[tx_record.id], queue=queue_name)

        return db_tx

    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/{transaction_id}", 
            summary="Get transaction details",
            description="Retrieves detailed information about a specific transaction by its ID, including its outputs and associated assets.",
            responses={
                200: {
                    "description": "Transaction details retrieved successfully",
                    "content": {
                        "application/json": {
                            "example": {
                                "id": "uuid",
                                "wallet_id": "uuid",
                                "metadata_json": {"1": "value"},
                                "status": "queued",
                                "created_at": "2023-10-01T00:00:00Z",
                                "updated_at": "2023-10-01T00:00:00Z",
                                "outputs": [
                                    {
                                        "address": "addr_test1...",
                                        "datum": None,
                                        "assets": [
                                            {"unit": "asset1", "quantity": 1000}
                                        ]
                                    }
                                ],
                                "mint": []
                            }
                        }
                    }
                },
                404: {
                    "description": "Transaction not found",
                    "content": {
                        "application/json": {
                            "example": {
                                "detail": "Transaction not found"
                            }
                        }
                    }
                },
                422: {
                    "description": "Validation error",
                    "content": {
                        "application/json": {
                            "example": {
                                "detail": "Validation error message"
                            }
                        }
                    }
                },                
                500: {
                    "description": "Internal server error",
                    "content": {
                        "application/json": {
                            "example": {
                                "detail": "error message"
                            }
                        }
                    }
                }
            },
            response_model=TransactionOut
            )
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