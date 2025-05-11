from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
from heron_app.db.database import Base

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wallet_id = Column(UUID(as_uuid=True), ForeignKey("wallets.id"), nullable=False)
    to_address = Column(String, nullable=False)
    amount_lovelace = Column(Integer, nullable=False)
    metadata_json = Column(JSON, nullable=True)
    status = Column(String, default="queued")
    tx_hash = Column(String, nullable=True)
    tx_fee = Column(Integer, nullable=True)
    tx_size = Column(Integer, nullable=True)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
