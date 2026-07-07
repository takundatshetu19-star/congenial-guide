from decimal import Decimal
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.user import User
from app.models.wallet import Wallet
from app.models.transaction import Transaction, TransactionType, TransactionStatus
from app.services.audit_service import log_deposit, log_transfer


def get_wallet_balance(db: Session, user: User) -> Wallet:
    """Get user's wallet balance"""
    wallet = db.query(Wallet).filter(Wallet.user_id == user.id).first()
    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found"
        )
    return wallet


def deposit(db: Session, user: User, amount: Decimal) -> Wallet:
    """Deposit money into user's wallet (concurrency-safe)."""
    # Validate amount
    if amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Deposit amount must be positive"
        )

    # Lock the wallet row to avoid race conditions in concurrent requests.
    # with_for_update() requires an active transaction; SQLAlchemy will handle it here.
    wallet = (
        db.query(Wallet)
        .with_for_update()
        .filter(Wallet.user_id == user.id)
        .first()
    )
    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found"
        )

    # Ensure Decimal arithmetic
    current_balance = Decimal(wallet.balance or 0)
    wallet.balance = current_balance + Decimal(amount)

    # Create transaction record
    transaction = Transaction(
        receiver_id=user.id,
        amount=Decimal(amount),
        transaction_type=TransactionType.DEPOSIT,
        status=TransactionStatus.COMPLETED,
        description="Deposit to wallet"
    )
    db.add(transaction)

    try:
        db.commit()
    except Exception:
        db.rollback()
        # mark transaction as failed in DB (if present) or raise
        # If transaction insertion failed, ensure we surface an error to caller
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete deposit"
        )

    # Refresh instances to get updated fields (e.g., ids, timestamps)
    db.refresh(wallet)
    db.refresh(transaction)

    # Attempt to write audit log. Audit failures shouldn't break the main flow,
    # but you may want to surface/monitor these.
    try:
        # Adjust the signature/arguments to match your audit_service implementation if necessary.
        # Expected: log_deposit(db_session, user_id, transaction_id, amount)
        log_deposit(db, user.id, transaction.id, Decimal(amount))
    except Exception:
        # swallow audit errors but you can log them to monitoring
        # e.g., logger.exception("Failed to write audit log for deposit")
        pass

    return wallet
