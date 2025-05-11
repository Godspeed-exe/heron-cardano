from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID

class TransactionCreate(BaseModel):
    wallet_id: UUID
    to_address: str
    amount_lovelace: int
    metadata: Optional[dict] = None

class TransactionOut(BaseModel):
    id: UUID
    wallet_id: UUID
    to_address: str
    amount_lovelace: int
    metadata_json: Optional[dict] = None
    status: str
    created_at: datetime
    tx_hash: Optional[str] = None
    tx_fee: Optional[int] = None
    tx_size: Optional[int] = None
    updated_at: datetime
    error_message: Optional[str] = None

    class Config:
        orm_mode = True