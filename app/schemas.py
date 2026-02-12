from pydantic import BaseModel, Field, field_validator
from typing import Optional
import re


class SendTxRequest(BaseModel):
    chain: str = Field(..., description="Blockchain chain")
    from_address: str = Field(..., description="Sender address")
    to_address: str = Field(..., description="Recipient address")
    value_wei: int = Field(..., description="Value in wei")
    data: str = Field(..., description="Transaction data")
    idempotency_key: Optional[str] = Field(None, description="Idempotency key")

    @field_validator("chain")
    @classmethod
    def validate_chain(cls, v):
        allowed = {"ethereum", "polygon", "sepolia"}
        if v not in allowed:
            raise ValueError(f"chain must be one of: {', '.join(allowed)}")
        return v

    @field_validator("from_address", "to_address")
    @classmethod
    def validate_address(cls, v):
        if not v.startswith("0x"):
            raise ValueError("address must start with 0x")
        if len(v) != 42:
            raise ValueError("address must be exactly 42 characters")
        # Check hex format
        try:
            int(v[2:], 16)
        except ValueError:
            raise ValueError("address must be valid hex")
        return v

    @field_validator("value_wei")
    @classmethod
    def validate_value(cls, v):
        if not isinstance(v, int) or v < 0:
            raise ValueError("value_wei must be a non-negative integer")
        return v

    @field_validator("data")
    @classmethod
    def validate_data(cls, v):
        if not v.startswith("0x"):
            raise ValueError("data must start with 0x")
        return v


class SendTxResponse(BaseModel):
    tx_id: str
    tx_hash: str
    status: str