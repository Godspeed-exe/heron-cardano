from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from heron_app.schemas.transaction_output import TransactionOutputSchema

class TransactionCreate(BaseModel):
    wallet_id: UUID
    outputs: List[TransactionOutputSchema]
    metadata: Optional[dict] = None

class TransactionOut(BaseModel):
    id: UUID
    wallet_id: UUID
    metadata_json: Optional[dict] = None
    status: str
    created_at: datetime
    tx_hash: Optional[str] = None
    tx_fee: Optional[int] = None
    tx_size: Optional[int] = None
    updated_at: datetime
    error_message: Optional[str] = None
    outputs: List[TransactionOutputSchema]

    class Config:
        orm_mode = True