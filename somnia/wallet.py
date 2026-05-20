"""
User wallet management for Somnia chain.
Each user gets a generated wallet on registration.
"""
from database import get_db, User
from somnia.client import somnia


def create_wallet_for_user(user_id: int) -> dict:
    """Generate a new Somnia wallet for a user and store it."""
    wallet = somnia.create_user_wallet()
    db = next(get_db())
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.somnia_address = wallet["address"]
            user.somnia_private_key = wallet["private_key"]
            db.commit()
        return wallet
    finally:
        db.close()


def get_user_wallet(user_id: int) -> dict | None:
    """Retrieve a user's Somnia wallet."""
    db = next(get_db())
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user and user.somnia_address:
            return {
                "address": user.somnia_address,
                "private_key": user.somnia_private_key,
            }
        return None
    finally:
        db.close()


def get_user_balance(user_id: int) -> int:
    """Get user's STT balance on Somnia chain."""
    wallet = get_user_wallet(user_id)
    if not wallet:
        return 0
    return somnia.get_balance(wallet["address"])


def ensure_user_wallet(user_id: int) -> dict:
    """Ensure user has a wallet, create one if missing."""
    wallet = get_user_wallet(user_id)
    if not wallet:
        wallet = create_wallet_for_user(user_id)
    return wallet
