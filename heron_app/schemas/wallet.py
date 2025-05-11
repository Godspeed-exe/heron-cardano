from pydantic import BaseModel

class WalletCreate(BaseModel):
    name: str
    mnemonic: str  # 'mnemonic', 'imported', etc.

class WalletOut(WalletCreate):
    id: str
    address: str