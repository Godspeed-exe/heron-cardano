from typing import List, Optional
from pydantic import BaseModel


class TransactionMint(BaseModel):
    policy_id: str
    asset_name: str  # Mapping of asset names to quantities
    quantity: int

    class Config:
        from_attributes = True