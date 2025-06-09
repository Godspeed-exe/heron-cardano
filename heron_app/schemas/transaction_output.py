from typing import List, Optional
from pydantic import BaseModel
from heron_app.schemas.transaction_output_asset import TransactionAssetSchema  # ✅ correct

class TransactionOutputSchema(BaseModel):
    address: str
    assets: List[TransactionAssetSchema]
    datum: Optional[dict] = None

    class Config:
        from_attributes = True