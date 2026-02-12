import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.sql import func
from app.database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    tx_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    chain = Column(String, nullable=False)
    from_address = Column(String, nullable=False)
    to_address = Column(String, nullable=False)
    value_wei = Column(Integer, nullable=False)
    data = Column(String, nullable=False)
    idempotency_key = Column(String, nullable=True)
    tx_hash = Column(String, nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        # Unique constraint for idempotency
        {"sqlite_autoincrement": True},
    )