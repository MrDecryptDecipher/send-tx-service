"""
Integration tests for the Send Transaction Service.

these tests verify the end-to-end functionality of the API, including:
- Successful transaction submission
- Idempotency handling (201 -> 200 transitions)
- Input validation
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch

from app.database import Base, get_db
from app.main import app
from app import rpc_client

# Setup in-memory SQLite database for testing
# We use check_same_thread=False to allow multiple threads (FastAPI + TestClient)
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override the database dependency to use the test database."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="function")
def client():
    """
    Fixture to provide a TestClient instance with a clean database.
    Creates tables before each test and drops them afterwards.
    """
    # Create tables
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c
    # Drop tables
    Base.metadata.drop_all(bind=engine)


def test_send_tx_idempotency(client):
    """
    Verify the idempotency contract of the /send-tx endpoint.
    
    Scenario:
        1. Client submits a valid transaction with a specific idempotency_key.
        2. Service processes it, creates a record, and returns 201 Created.
        3. Client submits the EXACT SAME request again (simulating retry).
        4. Service detects the duplicate key, prevents double-submission,
           and returns the *existing* record with 200 OK.
    """
    
    # Arrange
    # Mock the RPC client to return a deterministic hash for assertions
    mock_hash = "0x" + "a" * 64
    
    with patch.object(rpc_client.rpc_client, 'send_transaction', return_value=mock_hash):
        payload = {
            "chain": "sepolia",
            "from_address": "0x1111111111111111111111111111111111111111",
            "to_address": "0x2222222222222222222222222222222222222222",
            "value_wei": 1000000000000000,
            "data": "0x",
            "idempotency_key": "abc-123"
        }
        
        # Act 1: Initial Submission
        response1 = client.post("/send-tx", json=payload)
        
        # Assert 1: New Resource Created
        assert response1.status_code == 201
        data1 = response1.json()
        assert data1["tx_hash"] == mock_hash
        assert data1["status"] == "submitted"
        assert "tx_id" in data1
        tx_id_1 = data1["tx_id"]
        
        # Act 2: Duplicate Submission (Retry)
        response2 = client.post("/send-tx", json=payload)
        
        # Assert 2: Existing Resource Returned
        # The status code MUST be 200 to indicate no new resource was created
        assert response2.status_code == 200
        
        data2 = response2.json()
        assert data2["tx_hash"] == mock_hash
        assert data2["tx_id"] == tx_id_1  # Should be the SAME persistence ID
        assert data2["status"] == "submitted"
        
        # Verification: Ensure RPC was called exactly once to prove we didn't
        # re-submit to the blockchain node.
        rpc_client.rpc_client.send_transaction.assert_called_once()


def test_invalid_chain_returns_422(client):
    """Test using an unsupported chain returns a validation error."""
    payload = {
        "chain": "invalid_chain",
        "from_address": "0x1111111111111111111111111111111111111111",
        "to_address": "0x2222222222222222222222222222222222222222",
        "value_wei": 1000000000000000,
        "data": "0x"
    }
    
    response = client.post("/send-tx", json=payload)
    assert response.status_code == 422


def test_invalid_address_returns_422(client):
    """Test address validation ensures '0x' prefix."""
    payload = {
        "chain": "sepolia",
        "from_address": "1111111111111111111111111111111111111111",  # Missing 0x
        "to_address": "0x2222222222222222222222222222222222222222",
        "value_wei": 1000000000000000,
        "data": "0x"
    }
    
    response = client.post("/send-tx", json=payload)
    assert response.status_code == 422


def test_negative_value_returns_422(client):
    """Test validation prevents negative transaction values."""
    payload = {
        "chain": "sepolia",
        "from_address": "0x1111111111111111111111111111111111111111",
        "to_address": "0x2222222222222222222222222222222222222222",
        "value_wei": -1,
        "data": "0x"
    }
    
    response = client.post("/send-tx", json=payload)
    assert response.status_code == 422