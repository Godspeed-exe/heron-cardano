from pydantic import BaseModel, Field

class WalletCreate(BaseModel):
    name: str = Field(..., description="User-defined name for the wallet")
    mnemonic: str = Field(..., description="24-word BIP-39 mnemonic phrase used to generate the wallet keys")

    class Config:
        from_attributes = True
        
class WalletOut(WalletCreate):
    id: str
    address: str