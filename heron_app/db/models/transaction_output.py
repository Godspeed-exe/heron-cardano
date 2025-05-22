from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, JSON # type: ignore
from sqlalchemy.dialects.postgresql import UUID # type: ignore
from sqlalchemy.orm import relationship # type: ignore

import uuid
from datetime import datetime
from heron_app.db.database import Base
from heron_app.db.models.transaction_output_asset import TransactionOutputAsset

class TransactionOutput(Base):
    __tablename__ = "transaction_outputs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_id = Column(Integer, ForeignKey("transactions.numeric_id"), nullable=False)
    address = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


    assets = relationship("TransactionOutputAsset", backref="output", cascade="all, delete-orphan")
