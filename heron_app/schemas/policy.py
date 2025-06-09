from pydantic import BaseModel
from datetime import datetime

class CreatePolicyRequest(BaseModel):
    name: str
    lock_date: datetime | None = None
    
    class Config:
        from_attributes = True
class PolicyResponse(BaseModel):
    name: str
    policy_id: str
    locking_slot: int | None
    created_at: datetime