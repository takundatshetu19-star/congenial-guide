import uuid
from decimal import Decimal
from app.models.user import User
from app.models.wallet import Wallet
from app.models.transaction import Transaction, TransactionType, TransactionStatus
from app.services.wallet_service import deposit


def test_deposit_updates_balance_and_creates_transaction(db_session):
    # Arrange: create a user and wallet directly to avoid relying on helpers
    unique = uuid.uuid4().hex[:8]
    email = f"test_deposit_{unique}@example.com"
    username = f"test_deposit_{unique}"

    user = User(email=email, username=username, hashed_password="x", is_active=True)
    db_session.add(user)
    db_session.flush()  # populate user.id

    wallet = Wallet(user_id=user.id, balance=Decimal("0.00"))
    db_session.add(wallet)
    db_session.commit()

    db_session.refresh(user)

    # Act: deposit 100.50
    amount = Decimal("100.50")
    updated_wallet = deposit(db_session, user, amount)

    # Assert: wallet balance updated
    assert Decimal(updated_wallet.balance) == Decimal("100.50")

    # Assert: transaction exists
    tx = db_session.query(Transaction).filter(
        Transaction.receiver_id == user.id,
        Transaction.amount == amount,
        Transaction.transaction_type == TransactionType.DEPOSIT,
        Transaction.status == TransactionStatus.COMPLETED
    ).order_by(Transaction.id.desc()).first()

    assert tx is not None
    assert tx.receiver_id == user.id
    assert tx.amount == amount
    assert tx.transaction_type == TransactionType.DEPOSIT
    assert tx.status == TransactionStatus.COMPLETED
