from sqlalchemy import Column, String, DateTime # type: ignore
from sqlalchemy.dialects.postgresql import UUID # type: ignore
import uuid
from datetime import datetime
from heron_app.db.database import Base

class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    address = Column(String, nullable=False, unique=True)
    encrypted_root_key = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)