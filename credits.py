#!/usr/bin/env python3
"""
Utility module for handling user credit deductions and additions.

Provides functions `deduct_credits` and `add_credits` which safely modify a
user's credit balance, ensuring the user exists before committing the change
to the database.
"""

import logging
from typing import Optional

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("credits")

# The actual ORM setup (SQLAlchemy) and User model are assumed to exist
# elsewhere in the project. Adjust the import paths as needed.
try:
    from .database import SessionLocal  # type: ignore
    from .models import User, Transaction  # type: ignore
except ImportError as e:
    raise ImportError(
        "Required database session or User model could not be imported. "
        "Ensure `database.py` defines `SessionLocal` and `models.py` defines `User` and `Transaction`."
    ) from e


def deduct_credits(user_id: int, amount: int, description: str = "Service deduction") -> None:
    """
    Deduct a specified amount of credits from a user and log the transaction.
    """
    if amount <= 0:
        raise ValueError("Deduction amount must be a positive integer.")

    with SessionLocal() as db:
        user: Optional[User] = db.query(User).filter(User.id == user_id).first()

        if user is None:
            raise ValueError(f"User with id {user_id} not found.")

        if user.credits < amount:
            logger.error(f"DEDUCT FAILED: user {user_id} has {user.credits}, needs {amount}")
            raise ValueError(
                f"Insufficient credits: user has {user.credits}, attempted to deduct {amount}."
            )

        # Perform the deduction
        user.credits -= amount
        
        # Log transaction
        tx = Transaction(
            user_id=user_id,
            amount=-amount,
            description=description
        )
        db.add(tx)
        
        logger.info(f"DEDUCTED: {amount} from user {user_id}. New balance: {user.credits}")
        db.commit()


def add_credits(user_id: int, amount: int, description: str = "Credit addition") -> None:
    """
    Add a specified amount of credits to a user and log the transaction.
    """
    if amount <= 0:
        raise ValueError("Addition amount must be a positive integer.")

    with SessionLocal() as db:
        user: Optional[User] = db.query(User).filter(User.id == user_id).first()

        if user is None:
            raise ValueError(f"User with id {user_id} not found.")

        user.credits += amount
        
        # Log transaction
        tx = Transaction(
            user_id=user_id,
            amount=amount,
            description=description
        )
        db.add(tx)
        
        logger.info(f"ADDED: {amount} to user {user_id}. New balance: {user.credits}")
        db.commit()