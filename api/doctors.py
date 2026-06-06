"""
Doctors API endpoints for Doctors on Wheels.
Supports doctor listing, search, and details.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict

from database import get_db, Doctor, User
from auth import get_current_user
from api.storage import get_public_url, object_exists

router = APIRouter(prefix="/api/doctors", tags=["doctors"])


def get_doctor_avatar_url(user_id: int) -> str | None:
    """Get avatar URL from Filebase bucket if exists."""
    key = f"avatars/{user_id}.jpg"
    try:
        if object_exists(key):
            return get_public_url(key)
        return None
    except:
        return None


# Pydantic models
class DoctorResponse(BaseModel):
    id: int
    name: str
    specialty: str
    area: str
    bio: str | None
    rating: float
    review_count: int
    consultation_fee: int
    is_available: bool
    hpcsa_number: str | None = None
    practice_number: str | None = None
    verification_status: str = "pending"
    profile_completed: bool = False
    photo_url: str | None = None
    avatar_url: str | None = None
    # Gig Economy - Custom Pricing
    quick_chat_price: int | None = None
    video_call_price: int | None = None
    full_consultation_price: int | None = None
    prescription_review_price: int | None = None
    report_analysis_price: int | None = None
    peak_pricing_multiplier: float | None = None
    is_online: bool | None = None

    model_config = ConfigDict(from_attributes=True)


class DoctorDetailResponse(DoctorResponse):
    user_id: int | None = None

    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=List[DoctorResponse])
def list_doctors(
    specialty: Optional[str] = None,
    area: Optional[str] = None,
    online_only: bool = False,
    db: Session = Depends(get_db),
):
    """List all available doctors for patients."""
    doctors = db.query(Doctor).filter(Doctor.is_available == True).all()
    filtered_doctors = [
        doc for doc in doctors
        if doc.name != "AI Doctor"
    ]

    if online_only:
        filtered_doctors = [doc for doc in filtered_doctors if doc.is_online]

    if specialty:
        filtered_doctors = [
            doc for doc in filtered_doctors 
            if specialty.lower() in doc.specialty.lower()
        ]
    if area:
        filtered_doctors = [
            doc for doc in filtered_doctors 
            if area.lower() in doc.area.lower()
        ]

    # Add avatar URLs
    for doc in filtered_doctors:
        if doc.user_id:
            doc.avatar_url = get_doctor_avatar_url(doc.user_id)

    return filtered_doctors


@router.get("/{doctor_id}", response_model=DoctorDetailResponse)
def get_doctor(doctor_id: int, db: Session = Depends(get_db)):
    """Get detailed information for a specific doctor."""
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found"
        )

    # Add avatar URL
    if doctor.user_id:
        doctor.avatar_url = get_doctor_avatar_url(doctor.user_id)

    return doctor
