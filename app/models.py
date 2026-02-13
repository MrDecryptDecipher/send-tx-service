import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, UniqueConstraint
from sqlalchemy.sql import func
from app.database import Base


class Transaction(Base):
    """
    Represents a blockchain transaction record in the local database.

    This model serves as the source of truth for transaction status and ensures
    idempotency via a unique constraint on (chain, from_address, idempotency_key).
    """
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

    # We use __table_args__ to define composite constraints.
    # The UniqueConstraint here is critical for ensuring data integrity and
    # handling race conditions where application-level checks might pass
    # for concurrent duplicate requests.
    __table_args__ = (
        UniqueConstraint('chain', 'from_address', 'idempotency_key', name='_idempotency_uc'),
        {"sqlite_autoincrement": True},
    )