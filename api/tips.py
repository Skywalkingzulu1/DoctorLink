"""
Tip API endpoints for DoctorLink.
Tips go 100% to the doctor - platform does not take a cut.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict

from database import get_db, Tip, Appointment, Doctor, User
from auth import get_current_user

router = APIRouter(prefix="/api/tips", tags=["tips"])

MAX_TIP_AMOUNT = 500  # Maximum tip amount in credits


class CreateTipRequest(BaseModel):
    appointment_id: int
    amount: int


class TipResponse(BaseModel):
    id: int
    appointment_id: int
    patient_id: int
    doctor_id: int
    amount: int

    model_config = ConfigDict(from_attributes=True)


class TipBreakdownResponse(BaseModel):
    appointment_id: int
    base_price: int
    platform_fee: int  # 20%
    doctor_share: int  # 80%
    tip_amount: int
    total_to_doctor: int

    model_config = ConfigDict(from_attributes=True)


@router.post("", response_model=TipResponse, status_code=status.HTTP_201_CREATED)
def create_tip(
    request: CreateTipRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add a tip to a completed appointment. 100% goes to doctor."""
    if current_user.role != "PATIENT":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only patients can tip doctors",
        )

    # Validate amount
    if request.amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tip amount must be positive",
        )

    if request.amount > MAX_TIP_AMOUNT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tip amount cannot exceed {MAX_TIP_AMOUNT} credits",
        )

    # Check if user has enough credits
    if current_user.credits < request.amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient credits. Need {request.amount} credits.",
        )

    # Verify appointment exists and is completed
    appointment = (
        db.query(Appointment).filter(Appointment.id == request.appointment_id).first()
    )

    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )

    if appointment.patient_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only tip for your own appointments",
        )

    if appointment.status.value != "COMPLETED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only tip for completed appointments",
        )

    # Verify doctor exists
    doctor = db.query(Doctor).filter(Doctor.id == appointment.doctor_id).first()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found",
        )

    # Create tip
    tip = Tip(
        appointment_id=request.appointment_id,
        patient_id=current_user.id,
        doctor_id=doctor.id,
        amount=request.amount,
    )
    db.add(tip)

    # Deduct credits from patient
    current_user.credits -= request.amount

    # Add tip to appointment
    appointment.tip_amount = (appointment.tip_amount or 0) + request.amount

    # Add to doctor's pending earnings (100% to doctor)
    doctor.pending_earnings = (doctor.pending_earnings or 0) + request.amount
    doctor.total_earnings = (doctor.total_earnings or 0) + request.amount

    db.commit()
    db.refresh(tip)

    return tip


@router.get("/appointment/{appointment_id}", response_model=TipBreakdownResponse)
def get_tip_breakdown(
    appointment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get pricing breakdown for an appointment including tips."""
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()

    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )

    # Check access
    if current_user.role == "PATIENT" and appointment.patient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    base_price = appointment.base_price or appointment.price_credits or 150
    platform_fee = appointment.platform_fee or int(base_price * 0.20)
    doctor_share = base_price - platform_fee
    tip_amount = appointment.tip_amount or 0

    return TipBreakdownResponse(
        appointment_id=appointment_id,
        base_price=base_price,
        platform_fee=platform_fee,
        doctor_share=doctor_share,
        tip_amount=tip_amount,
        total_to_doctor=doctor_share + tip_amount,
    )


@router.get("/doctor/tips", response_model=List[TipResponse])
def get_doctor_tips(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all tips received by the current doctor."""
    if current_user.role != "DOCTOR":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only doctors can view their tips",
        )

    doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor profile not found",
        )

    tips = (
        db.query(Tip)
        .filter(Tip.doctor_id == doctor.id)
        .order_by(Tip.created_at.desc())
        .all()
    )

    return tips


@router.get("/doctor/tips/summary")
def get_doctor_tips_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get summary of doctor's tips."""
    if current_user.role != "DOCTOR":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only doctors can view their tips",
        )

    doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor profile not found",
        )

    tips = db.query(Tip).filter(Tip.doctor_id == doctor.id).all()

    total_tips = sum(tip.amount for tip in tips)
    tip_count = len(tips)
    average_tip = total_tips / tip_count if tip_count > 0 else 0

    return {
        "total_tips": total_tips,
        "tip_count": tip_count,
        "average_tip": int(average_tip),
    }


@router.get("/patient/tips", response_model=List[TipResponse])
def get_patient_tips(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all tips given by the current patient."""
    if current_user.role != "PATIENT":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only patients can view their tips",
        )

    tips = (
        db.query(Tip)
        .filter(Tip.patient_id == current_user.id)
        .order_by(Tip.created_at.desc())
        .all()
    )

    return tips
