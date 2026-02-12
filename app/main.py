from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.database import engine, Base, get_db
from app.models import Transaction
from app.schemas import SendTxRequest, SendTxResponse
from app.rpc_client import rpc_client

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Send Transaction Service")


@app.post("/send-tx", response_model=SendTxResponse, status_code=201)
def send_tx(request: SendTxRequest, db: Session = Depends(get_db)):
    """
    Submit a transaction. Supports idempotency via idempotency_key.
    """
    
    # Check idempotency if key provided
    if request.idempotency_key:
        existing = db.query(Transaction).filter(
            and_(
                Transaction.chain == request.chain,
                Transaction.from_address == request.from_address,
                Transaction.idempotency_key == request.idempotency_key
            )
        ).first()
        
        if existing:
            # Return existing transaction
            return SendTxResponse(
                tx_id=existing.tx_id,
                tx_hash=existing.tx_hash,
                status=existing.status
            )
    
    # Call stubbed RPC client
    tx_hash = rpc_client.send_transaction(
        chain=request.chain,
        from_addr=request.from_address,
        to_addr=request.to_address,
        value_wei=request.value_wei,
        data=request.data
    )
    
    # Create new transaction record
    db_tx = Transaction(
        chain=request.chain,
        from_address=request.from_address,
        to_address=request.to_address,
        value_wei=request.value_wei,
        data=request.data,
        idempotency_key=request.idempotency_key,
        tx_hash=tx_hash,
        status="submitted"
    )
    
    db.add(db_tx)
    db.commit()
    db.refresh(db_tx)
    
    return SendTxResponse(
        tx_id=db_tx.tx_id,
        tx_hash=db_tx.tx_hash,
        status=db_tx.status
    )


@app.get("/health")
def health_check():
    return {"status": "healthy"}