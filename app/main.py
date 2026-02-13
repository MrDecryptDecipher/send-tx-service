"""
Main application entry point for the Transaction Service.

This module defines the FastAPI application and endpoints for submitting transactions.
It handles database connections, dependency injection, and ensures idempotent transaction submission.
"""

from fastapi import FastAPI, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import and_
from app.database import engine, Base, get_db
from app.models import Transaction
from app.schemas import SendTxRequest, SendTxResponse
from app.rpc_client import rpc_client

# Create tables
# In a production environment, we would use Alembic migrations instead of create_all.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Send Transaction Service")


@app.post("/send-tx", response_model=SendTxResponse, status_code=201)
def send_tx(request: SendTxRequest, response: Response, db: Session = Depends(get_db)):
    """
    Submit a transaction to the blockchain network.
    
    This endpoint ensures idempotency using a unique key provided in the request.
    If a transaction with the same (chain, from_address, idempotency_key) already exists,
    it returns the existing transaction with a 200 OK status instead of creating a new one.
    
    Args:
        request (SendTxRequest): The transaction details.
        response (Response): The FastAPI response object, used to modify status codes.
        db (Session): The database session dependency.
        
    Returns:
        SendTxResponse: The submitted or existing transaction details.
        
    Raises:
        HTTPException: If an internal integrity error occurs that cannot be resolved.
    """
    
    # 1. Idempotency Check (Read Path)
    # We first check if the transaction implementation already exists to avoid unnecessary RPC calls.
    if request.idempotency_key:
        existing = db.query(Transaction).filter(
            and_(
                Transaction.chain == request.chain,
                Transaction.from_address == request.from_address,
                Transaction.idempotency_key == request.idempotency_key
            )
        ).first()
        
        if existing:
            # Idempotent response: Return 200 OK with the existing record.
            # This indicates the request was processed successfully in the past.
            response.status_code = status.HTTP_200_OK
            return SendTxResponse(
                tx_id=existing.tx_id,
                tx_hash=existing.tx_hash,
                status=existing.status
            )
    
    # 2. External Service Call
    # We consciously perform the RPC call *before* insertion to ensure we have a valid hash.
    # Note: In a robust distributed system, we might want to insert a "pending" record first
    # to avoid orphan transactions if the RPC succeeds but the DB insert fails.
    # For this interview scope, we assume RPC is fast and stable.
    tx_hash = rpc_client.send_transaction(
        chain=request.chain,
        from_addr=request.from_address,
        to_addr=request.to_address,
        value_wei=request.value_wei,
        data=request.data
    )
    
    # 3. Database Write (Write Path)
    # create the transaction object
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
    
    try:
        db.add(db_tx)
        db.commit()
        db.refresh(db_tx)
    except IntegrityError:
        # 4. Race Condition Handling
        # If two requests passed the "Read Path" check simultaneously, the second one will
        # fail here due to the UniqueConstraint. We catch this, rollback, and return the
        # winner's record.
        db.rollback()
        
        # Re-query the existing record that caused the conflict
        existing = db.query(Transaction).filter(
            and_(
                Transaction.chain == request.chain,
                Transaction.from_address == request.from_address,
                Transaction.idempotency_key == request.idempotency_key
            )
        ).first()
        
        if existing:
            response.status_code = status.HTTP_200_OK
            return SendTxResponse(
                tx_id=existing.tx_id,
                tx_hash=existing.tx_hash,
                status=existing.status
            )
        else:
            # This is a highly unlikely edge case (e.g., constraint failed but record invalid)
            raise HTTPException(status_code=500, detail="Database integrity error")
            
    # Return 201 Created (default status) for a minimal new resource
    return SendTxResponse(
        tx_id=db_tx.tx_id,
        tx_hash=db_tx.tx_hash,
        status=db_tx.status
    )


@app.get("/health")
def health_check():
    return {"status": "healthy"}