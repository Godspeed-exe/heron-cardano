from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, JSON # type: ignore
from sqlalchemy.dialects.postgresql import UUID # type: ignore
from sqlalchemy.orm import relationship # type: ignore

import uuid
from datetime import datetime
from heron_app.db.database import Base
from heron_app.db.models.transaction_output_asset import TransactionOutputAsset

class TransactionMint(Base):
    __tablename__ = "transaction_mints"

    id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_id = Column(Integer, ForeignKey("transactions.numeric_id"), nullable=False)
    policy_id = Column(String, ForeignKey("minting_policies.policy_id"), nullable=False)
    asset_name = Column(String, nullable=False)  # Name of the asset being minted
    quantity = Column(Integer, nullable=False)  # Quantity of the asset being minted
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
