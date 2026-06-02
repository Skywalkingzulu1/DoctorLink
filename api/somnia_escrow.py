"""
Somnia Escrow API endpoints for Doctors on Wheels.
Handles on-chain payment escrow for appointments.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db, User, Doctor, Appointment, EscrowStatus
from somnia.wallet import get_user_wallet, get_user_balance, ensure_user_wallet
from somnia.escrow_service import (
    deposit_escrow,
    release_escrow,
    refund_escrow,
    get_escrow_status,
)

router = APIRouter(prefix="/api/somnia/escrow", tags=["somnia-escrow"])


class DepositRequest(BaseModel):
    appointment_id: int
    amount: int


class EscrowStatusResponse(BaseModel):
    appointment_id: int
    deposited: int
    released: int
    state: str


@router.post("/deposit")
def deposit(
    request: DepositRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Deposit STT tokens into escrow for an appointment."""
    appointment = (
        db.query(Appointment)
        .filter(Appointment.id == request.appointment_id)
        .first()
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if appointment.patient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your appointment")

    doctor = db.query(Doctor).filter(Doctor.id == appointment.doctor_id).first()
    if not doctor or not doctor.user_id:
        raise HTTPException(status_code=400, detail="Doctor has no linked user account")
    doctor_wallet = get_user_wallet(doctor.user_id)
    doctor_address = (
        doctor_wallet["address"]
        if doctor_wallet
        else "0x0000000000000000000000000000000000000000"
    )

    # Check balance before deposit
    balance = get_user_balance(current_user.id)
    if balance < request.amount:
        from somnia.client import somnia
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient STT balance. Have {somnia.w3.from_wei(balance, 'ether'):.4f} STT, need {somnia.w3.from_wei(request.amount, 'ether'):.4f} STT",
        )

    result = deposit_escrow(request.appointment_id, doctor_address, request.amount)

    appointment.escrow_status = EscrowStatus.HELD
    appointment.somnia_tx_hash = result["tx_hash"]
    db.commit()

    return {
        "message": "Escrow deposited",
        "tx_hash": result["tx_hash"],
        "appointment_id": request.appointment_id,
    }


@router.post("/release/{appointment_id}")
def release(
    appointment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Release escrow to doctor after appointment completion."""
    appointment = (
        db.query(Appointment).filter(Appointment.id == appointment_id).first()
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if current_user.role not in ("DOCTOR", "ADMIN"):
        raise HTTPException(status_code=403, detail="Only doctors can release escrow")

    result = release_escrow(appointment_id)

    appointment.escrow_status = EscrowStatus.RELEASED
    appointment.somnia_release_tx = result["tx_hash"]
    db.commit()

    return {
        "message": "Escrow released",
        "tx_hash": result["tx_hash"],
    }


@router.post("/refund/{appointment_id}")
def refund(
    appointment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Refund escrow to patient on cancellation."""
    appointment = (
        db.query(Appointment).filter(Appointment.id == appointment_id).first()
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    result = refund_escrow(appointment_id)

    appointment.escrow_status = EscrowStatus.REFUNDED
    appointment.somnia_refund_tx = result["tx_hash"]
    db.commit()

    return {
        "message": "Escrow refunded",
        "tx_hash": result["tx_hash"],
    }


@router.get("/status/{appointment_id}", response_model=EscrowStatusResponse)
def status(appointment_id: int):
    """Get on-chain escrow status."""
    result = get_escrow_status(appointment_id)
    return EscrowStatusResponse(**result)


@router.get("/wallet/balance")
def get_wallet_balance(current_user: User = Depends(get_current_user)):
    """Get user's STT balance on Somnia chain."""
    wallet = ensure_user_wallet(current_user.id)
    balance_wei = get_user_balance(current_user.id)
    from somnia.client import somnia
    return {
        "address": wallet["address"],
        "balance_wei": balance_wei,
        "balance_eth": float(somnia.w3.from_wei(balance_wei, "ether")),
    }


@router.post("/wallet/create")
def create_wallet(current_user: User = Depends(get_current_user)):
    """Create a new Somnia wallet for the current user."""
    wallet = ensure_user_wallet(current_user.id)
    return {
        "address": wallet["address"],
        "message": "Wallet created successfully",
    }
