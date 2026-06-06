"""
Doctor subscription API on Somnia.
Doctors pay 10 STT/month for AI tools subscription.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel
from sqlalchemy.orm import Session
from web3 import Web3

from auth import get_current_user
from database import get_db, User, Doctor
from somnia.client import somnia
from config import settings

SUBSCRIPTION_PRICE_STT = 10  # 10 STT/month
SUBSCRIPTION_DURATION_DAYS = 30

router = APIRouter(prefix="/api/somnia/subscription", tags=["somnia-subscription"])


class SubscribeRequest(BaseModel):
    tx_hash: str


class SubscriptionStatus(BaseModel):
    active: bool
    end_date: str = None
    stt_paid: float = 0


@router.post("/subscribe")
def subscribe(
    request: SubscribeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Doctor subscribes by sending 10 STT to the sponsor contract."""
    if current_user.role != "DOCTOR":
        raise HTTPException(status_code=403, detail="Only doctors can subscribe")

    doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor profile not found")

    # Verify the transaction
    tx_hash = request.tx_hash
    try:
        receipt = somnia.w3.eth.get_transaction_receipt(tx_hash)
        if receipt is None:
            raise HTTPException(status_code=400, detail="Transaction not found")
        if receipt.get("status") != 1:
            raise HTTPException(status_code=400, detail="Transaction failed")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid transaction: {str(e)}")

    # Verify it was sent to the sponsor contract
    tx = somnia.w3.eth.get_transaction(tx_hash)
    sponsor_addr = Web3.to_checksum_address(settings.SOMNIA_SPONSOR_CONTRACT)
    if tx.get("to") != sponsor_addr:
        raise HTTPException(status_code=400, detail="Transaction not sent to sponsor contract")

    # Check amount
    value = tx.get("value", 0)
    if value < somnia.w3.to_wei(SUBSCRIPTION_PRICE_STT, "ether"):
        raise HTTPException(status_code=400, detail=f"Must send at least {SUBSCRIPTION_PRICE_STT} STT")

    # Record subscription
    now = datetime.now(timezone.utc)
    end_date = now + timedelta(days=SUBSCRIPTION_DURATION_DAYS)

    setattr(doctor, "subscription_active", True)
    setattr(doctor, "subscription_end", end_date)
    setattr(doctor, "subscription_stt_paid", float(somnia.w3.from_wei(value, "ether")))
    db.commit()

    return {
        "message": "Subscription activated!",
        "end_date": end_date.isoformat(),
    }


@router.get("/status")
def get_subscription_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Check subscription status."""
    if current_user.role != "DOCTOR":
        return {"active": False, "reason": "Patient accounts don't need subscriptions"}

    doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
    if not doctor:
        return {"active": False, "reason": "Doctor profile not found"}

    end_date = getattr(doctor, "subscription_end", None)
    active = getattr(doctor, "subscription_active", False)

    # Auto-expire
    if active and end_date and end_date < datetime.now(timezone.utc):
        setattr(doctor, "subscription_active", False)
        db.commit()
        active = False

    return {
        "active": active,
        "end_date": end_date.isoformat() if end_date else None,
        "stt_paid": getattr(doctor, "subscription_stt_paid", 0),
    }
