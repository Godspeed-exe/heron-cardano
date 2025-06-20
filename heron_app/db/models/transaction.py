from sqlalchemy import Column, String, Sequence,  Integer, DateTime, ForeignKey, JSON, func  # type: ignore
import sqlalchemy as sa # type: ignore
from sqlalchemy.orm import relationship # type: ignore
from sqlalchemy.dialects.postgresql import UUID # type: ignore
import uuid
from datetime import datetime
from heron_app.db.database import Base
from heron_app.db.models.transaction_output import TransactionOutput

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    numeric_id = Column(
        Integer,
        Sequence("transaction_numeric_id_seq"),
        autoincrement=True,
        nullable=False,
        unique=True
    )
    wallet_id = Column(UUID(as_uuid=True), ForeignKey("wallets.id"), nullable=False)
    metadata_json = Column(JSON, nullable=True)
    status = Column(String, default="queued")
    tx_hash = Column(String, nullable=True)
    tx_fee = Column(Integer, nullable=True)
    tx_size = Column(Integer, nullable=True)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    retries = Column(Integer, default=0)
    confirmed_at = Column(DateTime, nullable=True)
    outputs = relationship("TransactionOutput", backref="transaction", cascade="all, delete-orphan")
