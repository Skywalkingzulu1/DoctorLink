"""
Credit and Payment API endpoints for DoctorLink.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import List
import hashlib
import urllib.parse
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db, User, Transaction, Doctor
from auth import get_current_user
from config import settings

router = APIRouter(prefix="/api/credits", tags=["credits", "payments"])


class CreditBalanceResponse(BaseModel):
    credits: int


class TransactionResponse(BaseModel):
    id: int
    amount: int
    transaction_type: str
    description: str | None
    payment_status: str
    created_at: str

    class Config:
        from_attributes = True


class PurchaseCreditsRequest(BaseModel):
    amount: int
    payment_method: str = "manual"  # payfast, manual


class PayFastPaymentRequest(BaseModel):
    amount: int


@router.get("/balance", response_model=CreditBalanceResponse)
def get_balance(current_user: User = Depends(get_current_user)):
    """Get current credit balance."""
    return {"credits": current_user.credits}


@router.get("/transactions", response_model=List[TransactionResponse])
def list_transactions(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """List credit transactions for current user."""
    transactions = (
        db.query(Transaction)
        .filter(Transaction.user_id == current_user.id)
        .order_by(Transaction.created_at.desc())
        .all()
    )
    return [
        {
            "id": t.id,
            "user_id": t.user_id,
            "amount": t.amount,
            "transaction_type": t.transaction_type or "",
            "description": t.description,
            "payment_method": t.payment_method,
            "payment_status": t.payment_status or "pending",
            "payfast_payment_id": t.payfast_payment_id,
            "created_at": t.created_at.isoformat() if t.created_at else "",
        }
        for t in transactions
    ]


@router.post("/purchase")
def purchase_credits(
    request: PurchaseCreditsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Purchase credits (demo mode - instant)."""
    if request.amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid amount"
        )

    # Add credits
    current_user.credits += request.amount

    # Record transaction
    transaction = Transaction(
        user_id=current_user.id,
        amount=request.amount,
        transaction_type="credit_purchase",
        description=f"Purchased {request.amount} credits",
        payment_status="completed",
    )
    db.add(transaction)
    db.commit()

    return {
        "message": f"Successfully purchased {request.amount} credits",
        "new_balance": current_user.credits,
    }


@router.post("/payfast/initiate")
def initiate_payfast_payment(
    request: PayFastPaymentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Initiate PayFast payment."""
    if request.amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid amount"
        )

    # Create pending transaction
    transaction = Transaction(
        user_id=current_user.id,
        amount=request.amount,
        transaction_type="credit_purchase",
        description=f"PayFast payment for {request.amount} credits",
        payment_status="pending",
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    # Build PayFast payment URL
    pf_data = {
        "merchant_id": settings.PAYFAST_MERCHANT_ID or "10000100",
        "merchant_key": "46f0cd6945815a",
        "return_url": settings.PAYFAST_RETURN_URL,
        "cancel_url": settings.PAYFAST_CANCEL_URL,
        "notify_url": settings.PAYFAST_NOTIFY_URL,
        "m_payment_id": str(transaction.id),
        "amount": str(request.amount),
        "item_name": f"DoctorLink Credits - {request.amount} credits",
        "item_description": f"Purchase of {request.amount} credits for DoctorLink",
        "email_confirmation": "1",
        "confirmation_address": current_user.email,
    }

    # Generate signature
    pf_data["signature"] = generate_payfast_signature(pf_data)

    # Build payment URL
    payment_url = settings.PAYFAST_PAYMENT_URL + "?" + urllib.parse.urlencode(pf_data)

    return {
        "payment_url": payment_url,
        "transaction_id": transaction.id,
        "amount": request.amount,
    }


@router.get("/payfast/return")
def payfast_return(
    payment_id: str = Query(..., alias="m_payment_id"),
    pf_payment_id: str = Query(None, alias="pf_payment_id"),
    db: Session = Depends(get_db),
):
    """Handle PayFast payment return."""
    transaction = (
        db.query(Transaction).filter(Transaction.id == int(payment_id)).first()
    )
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found"
        )

    # Update transaction
    transaction.payment_status = "completed"
    transaction.payfast_payment_id = pf_payment_id

    # Add credits to user
    user = db.query(User).filter(User.id == transaction.user_id).first()
    if user:
        user.credits += transaction.amount

    db.commit()

    return {"message": "Payment successful", "credits": user.credits if user else 0}


@router.get("/payfast/cancel")
def payfast_cancel(payment_id: str = Query(..., alias="m_payment_id")):
    """Handle PayFast payment cancellation."""
    return {"message": "Payment cancelled"}


@router.post("/payfast/notify")
def payfast_notify(
    pf_payment_id: str = None, m_payment_id: str = None, db: Session = Depends(get_db)
):
    """Handle PayFast payment notification (webhook)."""
    # In production, verify the signature
    if m_payment_id:
        transaction = (
            db.query(Transaction).filter(Transaction.id == int(m_payment_id)).first()
        )
        if transaction and transaction.payment_status == "pending":
            transaction.payment_status = "completed"

            user = db.query(User).filter(User.id == transaction.user_id).first()
            if user:
                user.credits += transaction.amount

            db.commit()

    return {"status": "OK"}


def generate_payfast_signature(data: dict) -> str:
    """Generate PayFast signature."""
    pf_string = "&".join([f"{k}={v}" for k, v in sorted(data.items()) if v])
    if settings.PAYFAST_PASS_PHRASE:
        pf_string += f"&passphrase={settings.PAYFAST_PASS_PHRASE}"
    return hashlib.md5(pf_string.encode()).hexdigest()


# Doctor earnings endpoint
@router.get("/doctor/earnings")
def get_doctor_earnings(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Get doctor earnings (total and pending)."""
    if current_user.role != "DOCTOR":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only doctors can access earnings",
        )

    doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Doctor profile not found"
        )

    return {
        "total_earnings": doctor.total_earnings or 0,
        "pending_earnings": doctor.pending_earnings or 0,
    }


@router.post("/doctor/collect")
def collect_earnings(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Transfer pending earnings to doctor's wallet."""
    if current_user.role != "DOCTOR":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only doctors can collect earnings",
        )

    doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Doctor profile not found"
        )

    pending = doctor.pending_earnings or 0
    if pending == 0:
        return {"message": "No pending earnings to collect"}

    # Transfer to wallet
    current_user.credits += pending
    doctor.pending_earnings = 0

    # Record transaction
    transaction = Transaction(
        user_id=current_user.id,
        amount=pending,
        transaction_type="earnings_collected",
        description=f"Collected {pending} credits from appointments",
        payment_status="completed",
    )
    db.add(transaction)
    db.commit()

    return {
        "message": f"Collected {pending} credits",
        "new_balance": current_user.credits,
    }
