from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, JSON # type: ignore
from sqlalchemy.dialects.postgresql import UUID # type: ignore
import uuid
from datetime import datetime
from heron_app.db.database import Base


class TransactionOutputAsset(Base):
    __tablename__ = "transaction_output_assets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    output_id = Column(Integer, ForeignKey("transaction_outputs.id"), nullable=False)
    unit = Column(String, nullable=False)  # 'lovelace', 'policyid.assetname'
    quantity = Column(String, nullable=False)  # store as string to avoid int overflow
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
