# Send Transaction Service

A minimal FastAPI service for submitting blockchain transactions with idempotency support.

## Features

- **POST /send-tx**: Submit transactions to ethereum, polygon, or sepolia chains
- **Idempotency**: Uses `idempotency_key` to prevent duplicate transactions
- **Validation**: Strict input validation with 422 errors for invalid data
- **Stubbed RPC**: Simulates blockchain calls without real network requests

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the Server

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

### 3. Run Tests

```bash
pytest
```
