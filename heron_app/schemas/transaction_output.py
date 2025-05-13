from typing import List
from pydantic import BaseModel
from heron_app.schemas.transaction_output_asset import TransactionAssetSchema  # ✅ correct

class TransactionOutputSchema(BaseModel):
    address: str
    assets: List[TransactionAssetSchema]

    class Config:
        orm_mode = True