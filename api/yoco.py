"""
Official Yoco Payment Integration for DoctorLink.
Handles fiat checkout via Yoco API and automatic on-chain escrow funding.
"""
import os
import json
import requests
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from auth import get_current_user
from database import get_db, User, Appointment, EscrowStatus, Transaction, Doctor
from somnia.wallet import ensure_user_wallet, get_user_wallet
from somnia.escrow_service import deposit_escrow
from config import settings
from somnia.client import somnia

router = APIRouter(prefix="/api/yoco", tags=["yoco-payment"])

# Yoco API Endpoints
YOCO_API_LEGACY = "https://payments.yoco.com/api/checkouts"

class YocoInitiateRequest(BaseModel):
    appointment_id: int
    amount_zar: float

@router.post("/initiate")
def initiate_yoco_payment(
    request: YocoInitiateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Initiate a real Yoco checkout session for an appointment."""
    appointment = db.query(Appointment).filter(Appointment.id == request.appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    # Create a pending transaction in our DB
    transaction = Transaction(
        user_id=current_user.id,
        appointment_id=appointment.id,
        amount=int(request.amount_zar),
        currency="ZAR",
        transaction_type="appointment_payment",
        payment_method="yoco",
        payment_status="pending",
        description=f"Yoco payment for appointment #{appointment.id}"
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    # Prepare Yoco API Request as per official docs
    amount_cents = int(request.amount_zar * 100)
    
    payload = {
        "amount": amount_cents,
        "currency": "ZAR",
        # Including metadata so the webhook can identify the transaction
        "metadata": {
            "transaction_id": str(transaction.id),
            "appointment_id": str(appointment.id)
        }
    }
    
    headers = {
        "Authorization": f"Bearer {settings.YOCO_SECRET_KEY}",
        "Content-Type": "application/json"
    }

    error_detail = "Unknown error"
    try:
        # Fallback for demo if no real secret key
        is_placeholder = "sk_test_..." in settings.YOCO_SECRET_KEY or len(settings.YOCO_SECRET_KEY) < 10
        if is_placeholder:
             return {
                "transaction_id": transaction.id,
                "checkout_url": f"/static/index.html?mock_yoco={transaction.id}&appt={appointment.id}",
                "mode": "mock",
                "message": "Demo Mode: Redirecting to simulated Yoco checkout."
            }

        # Use the official endpoint from the Yoco docs
        print(f"[Yoco] Attempting checkout via {YOCO_API_LEGACY}")
        response = requests.post(YOCO_API_LEGACY, json=payload, headers=headers, timeout=10)
            
        if not response.ok:
            error_detail = response.text
            print(f"[Yoco] API Failure: {response.status_code} - {error_detail}")
            response.raise_for_status()
            
        yoco_data = response.json()
        
        # Look for redirectUrl
        redirect_url = yoco_data.get("redirectUrl")
        
        if not redirect_url:
            raise ValueError(f"Yoco response missing redirectUrl: {yoco_data}")

        return {
            "transaction_id": transaction.id,
            "checkout_url": redirect_url,
            "mode": "live"
        }
    except Exception as e:
        print(f"[Yoco] API Error: {e} | Detail: {error_detail}")
        
        # Determine error reason for the frontend
        error_msg = str(e)
        if "403" in error_msg or "Forbidden" in error_detail:
            error_msg = "Account_Not_Activated_For_Online_Payments_(403)"
            
        return {
            "transaction_id": transaction.id,
            "checkout_url": f"/static/yoco_checkout.html?amount={request.amount_zar}&transaction_id={transaction.id}&appt_id={appointment.id}&yoco_error={error_msg}",
            "mode": "mock",
            "message": f"Payment gateway error. Detail: {error_detail}"
        }

@router.post("/webhook")
async def yoco_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle Yoco payment success webhook and fund on-chain escrow."""
    try:
        payload = await request.json()
        event_type = payload.get("type")
        
        if event_type == "payment.succeeded":
            data = payload.get("payload", {})
            metadata = data.get("metadata", {})
            transaction_id = metadata.get("transaction_id")
            
            if not transaction_id:
                return {"status": "ignored", "reason": "no transaction id in metadata"}

            transaction = db.query(Transaction).filter(Transaction.id == int(transaction_id)).first()
            if transaction and transaction.payment_status == "pending":
                transaction.payment_status = "completed"
                
                # Payment successful! Now trigger on-chain escrow
                appointment = db.query(Appointment).filter(Appointment.id == transaction.appointment_id).first()
                if appointment:
                    try:
                        # Find doctor's wallet
                        doctor_profile = db.query(Doctor).filter(Doctor.id == appointment.doctor_id).first()
                        doctor_user = db.query(User).filter(User.id == doctor_profile.user_id).first()
                        doctor_wallet = get_user_wallet(doctor_user.id)
                        
                        # Platform funds the escrow in STT (1 ZAR = 1 STT for high-authority platform pooling)
                        # Ensure deployer has enough STT!
                        stt_amount_wei = int((appointment.base_price or 800) * 10**18)
                        
                        result = deposit_escrow(appointment.id, doctor_wallet["address"], stt_amount_wei)
                        
                        appointment.escrow_status = EscrowStatus.HELD
                        appointment.somnia_tx_hash = result["tx_hash"]
                        appointment.payment_method = "yoco"
                        
                        print(f"[Yoco] SUCCESS: Transaction {transaction_id} verified. Escrow {result['tx_hash']} funded.")
                    except Exception as escrow_err:
                        # If balance is low, this will fail. Return helpful message.
                        dep_addr = somnia.account.address if somnia.account else "unknown"
                        print(f"[Yoco] Fiat paid but Escrow funding failed. Deployer {dep_addr} may need STT. Error: {escrow_err}")
                
                db.commit()
                return {"status": "success"}

    except Exception as e:
        print(f"[Yoco] Webhook processing error: {e}")
        raise HTTPException(status_code=400, detail="Invalid webhook payload")

    return {"status": "ignored"}
