import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch, MagicMock

from app.database import Base, get_db
from app.main import app
from app import rpc_client

# Setup test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="function")
def client():
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)


def test_send_tx_idempotency(client):
    """
    Test that:
    1. First call returns 201 with tx_hash
    2. Second call with same idempotency_key returns 200 with same tx_hash and tx_id
    """
    
    # Mock the RPC client to return deterministic hash
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
        
        # First call - should create new transaction (201)
        response1 = client.post("/send-tx", json=payload)
        assert response1.status_code == 201
        
        data1 = response1.json()
        assert data1["tx_hash"] == mock_hash
        assert data1["status"] == "submitted"
        assert "tx_id" in data1
        tx_id_1 = data1["tx_id"]
        
        # Second call with same idempotency_key - should return existing (200)
        response2 = client.post("/send-tx", json=payload)
        assert response2.status_code == 200
        
        data2 = response2.json()
        assert data2["tx_hash"] == mock_hash
        assert data2["tx_id"] == tx_id_1  # Same ID
        assert data2["status"] == "submitted"
        
        # Verify RPC client was only called once (idempotency worked)
        # The mock tracks calls, so we can verify it was called once
        rpc_client.rpc_client.send_transaction.assert_called_once()


def test_invalid_chain_returns_422(client):
    """Test validation: invalid chain returns 422"""
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
    """Test validation: address not starting with 0x returns 422"""
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
    """Test validation: negative value_wei returns 422"""
    payload = {
        "chain": "sepolia",
        "from_address": "0x1111111111111111111111111111111111111111",
        "to_address": "0x2222222222222222222222222222222222222222",
        "value_wei": -1,
        "data": "0x"
    }
    
    response = client.post("/send-tx", json=payload)
    assert response.status_code == 422