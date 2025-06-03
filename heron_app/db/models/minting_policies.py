from sqlalchemy import Column, String, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID
from heron_app.db.database import Base
import uuid
from datetime import datetime

class MintingPolicy(Base):
    __tablename__ = "minting_policies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, unique=True, nullable=False)
    policy_id = Column(String, unique=True, nullable=False)
    encrypted_policy_skey = Column(String, nullable=False)
    locking_slot = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)