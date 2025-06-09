from pydantic import BaseModel

class TransactionAssetSchema(BaseModel):
    unit: str  # e.g. "lovelace", or "policyid.assetname"
    quantity: str  # String to support large values

    class Config:
        from_attributes = True