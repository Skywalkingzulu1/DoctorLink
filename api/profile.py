"""
Doctor Profile API endpoints for DoctorLink.
Gig Economy: Custom pricing, service tiers, gig mode toggle
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db, Doctor, User
from auth import get_current_user

router = APIRouter(prefix="/api/profile", tags=["profile"])


class DoctorPricingUpdate(BaseModel):
    quick_chat_price: int | None = None
    video_call_price: int | None = None
    full_consultation_price: int | None = None
    prescription_review_price: int | None = None
    report_analysis_price: int | None = None
    peak_pricing_multiplier: float | None = None


class DoctorGigModeUpdate(BaseModel):
    is_online: bool | None = None
    gig_mode_enabled: bool | None = None


class DoctorProfileUpdate(BaseModel):
    name: str | None = None
    specialty: str | None = None
    area: str | None = None
    bio: str | None = None
    consultation_fee: int | None = None
    hpcsa_number: str | None = None
    id_number: str | None = None
    photo_url: str | None = None


class DoctorProfileResponse(BaseModel):
    id: int
    user_id: int | None
    name: str
    specialty: str
    area: str
    bio: str | None
    rating: float
    review_count: int
    consultation_fee: int
    is_available: bool
    hpcsa_number: str | None
    id_number: str | None
    verification_status: str
    profile_completed: bool
    photo_url: str | None
    # Gig Economy fields
    quick_chat_price: int | None = None
    video_call_price: int | None = None
    full_consultation_price: int | None = None
    prescription_review_price: int | None = None
    report_analysis_price: int | None = None
    peak_pricing_multiplier: float | None = None
    is_online: bool | None = None
    gig_mode_enabled: bool | None = None

    class Config:
        from_attributes = True


class DoctorPricingResponse(BaseModel):
    quick_chat_price: int
    video_call_price: int
    full_consultation_price: int
    prescription_review_price: int
    report_analysis_price: int
    peak_pricing_multiplier: float
    effective_prices: dict

    class Config:
        from_attributes = True


@router.get("/doctor", response_model=DoctorProfileResponse)
def get_my_doctor_profile(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Get current doctor's profile with gig economy settings."""
    if current_user.role != "DOCTOR":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only doctors can access this endpoint",
        )

    doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Doctor profile not found"
        )

    return doctor


@router.put("/doctor", response_model=DoctorProfileResponse)
def update_doctor_profile(
    request: DoctorProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update current doctor's profile."""
    if current_user.role != "DOCTOR":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only doctors can access this endpoint",
        )

    doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Doctor profile not found"
        )

    # Update basic fields
    if request.name is not None:
        doctor.name = request.name
    if request.specialty is not None:
        doctor.specialty = request.specialty
    if request.area is not None:
        doctor.area = request.area
    if request.bio is not None:
        doctor.bio = request.bio
    if request.consultation_fee is not None:
        doctor.consultation_fee = request.consultation_fee
    if request.hpcsa_number is not None:
        doctor.hpcsa_number = request.hpcsa_number
    if request.id_number is not None:
        doctor.id_number = request.id_number
    if request.photo_url is not None:
        doctor.photo_url = request.photo_url

    # Mark profile as completed if basic fields are set
    if doctor.name and doctor.specialty and doctor.area:
        doctor.profile_completed = True
        if doctor.verification_status == "pending":
            doctor.verification_status = "basic"

    db.commit()
    db.refresh(doctor)

    return doctor


@router.post("/doctor/pricing", response_model=DoctorPricingResponse)
def update_doctor_pricing(
    request: DoctorPricingUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update doctor's custom pricing for service tiers."""
    if current_user.role != "DOCTOR":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only doctors can update pricing",
        )

    doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Doctor profile not found"
        )

    # Update pricing fields
    if request.quick_chat_price is not None:
        doctor.quick_chat_price = request.quick_chat_price
    if request.video_call_price is not None:
        doctor.video_call_price = request.video_call_price
    if request.full_consultation_price is not None:
        doctor.full_consultation_price = request.full_consultation_price
    if request.prescription_review_price is not None:
        doctor.prescription_review_price = request.prescription_review_price
    if request.report_analysis_price is not None:
        doctor.report_analysis_price = request.report_analysis_price
    if request.peak_pricing_multiplier is not None:
        doctor.peak_pricing_multiplier = request.peak_pricing_multiplier

    db.commit()
    db.refresh(doctor)

    # Calculate effective prices (with peak multiplier if applicable)
    multiplier = doctor.peak_pricing_multiplier or 1.0
    effective_prices = {
        "quick_chat": int(doctor.quick_chat_price * multiplier),
        "video_call": int(doctor.video_call_price * multiplier),
        "full_consultation": int(doctor.full_consultation_price * multiplier),
        "prescription_review": int(doctor.prescription_review_price * multiplier),
        "report_analysis": int(doctor.report_analysis_price * multiplier),
    }

    return DoctorPricingResponse(
        quick_chat_price=doctor.quick_chat_price,
        video_call_price=doctor.video_call_price,
        full_consultation_price=doctor.full_consultation_price,
        prescription_review_price=doctor.prescription_review_price,
        report_analysis_price=doctor.report_analysis_price,
        peak_pricing_multiplier=doctor.peak_pricing_multiplier or 1.0,
        effective_prices=effective_prices,
    )


@router.get("/doctor/pricing", response_model=DoctorPricingResponse)
def get_doctor_pricing(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current doctor's pricing configuration."""
    if current_user.role != "DOCTOR":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only doctors can access pricing",
        )

    doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Doctor profile not found"
        )

    # Calculate effective prices
    multiplier = doctor.peak_pricing_multiplier or 1.0
    effective_prices = {
        "quick_chat": int(doctor.quick_chat_price * multiplier),
        "video_call": int(doctor.video_call_price * multiplier),
        "full_consultation": int(doctor.full_consultation_price * multiplier),
        "prescription_review": int(doctor.prescription_review_price * multiplier),
        "report_analysis": int(doctor.report_analysis_price * multiplier),
    }

    return DoctorPricingResponse(
        quick_chat_price=doctor.quick_chat_price,
        video_call_price=doctor.video_call_price,
        full_consultation_price=doctor.full_consultation_price,
        prescription_review_price=doctor.prescription_review_price,
        report_analysis_price=doctor.report_analysis_price,
        peak_pricing_multiplier=doctor.peak_pricing_multiplier or 1.0,
        effective_prices=effective_prices,
    )


@router.post("/doctor/gig-mode")
def update_gig_mode(
    request: DoctorGigModeUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update gig mode (go online/offline)."""
    if current_user.role != "DOCTOR":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only doctors can update gig mode",
        )

    doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Doctor profile not found"
        )

    if request.is_online is not None:
        doctor.is_online = request.is_online
        status_text = "online" if request.is_online else "offline"

    if request.gig_mode_enabled is not None:
        doctor.gig_mode_enabled = request.gig_mode_enabled

    db.commit()
    db.refresh(doctor)

    return {
        "message": f"Doctor is now {status_text}",
        "is_online": doctor.is_online,
        "gig_mode_enabled": doctor.gig_mode_enabled,
    }


@router.get("/doctor/gig-mode")
def get_gig_mode(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current gig mode status."""
    if current_user.role != "DOCTOR":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only doctors can access gig mode",
        )

    doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Doctor profile not found"
        )

    return {
        "is_online": doctor.is_online,
        "gig_mode_enabled": doctor.gig_mode_enabled,
    }


@router.post("/doctor/request-verification")
def request_verification(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Request full verification (submits for admin review)."""
    if current_user.role != "DOCTOR":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only doctors can request verification",
        )

    doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Doctor profile not found"
        )

    if not doctor.profile_completed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please complete your profile first",
        )

    # Check if they have HPCSA number for full verification
    if doctor.hpcsa_number:
        doctor.verification_status = "verified"
        return {
            "message": "Verification approved!",
            "status": doctor.verification_status,
        }
    else:
        doctor.verification_status = "pending"
        return {
            "message": "Verification request submitted. Please add your HPCSA number for full verification.",
            "status": doctor.verification_status,
        }
