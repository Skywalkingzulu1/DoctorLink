"""
Doctor API endpoints for DoctorLink.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db, Doctor, User
from auth import get_current_user

router = APIRouter(prefix="/api/doctors", tags=["doctors"])


# Filebase config
FILEBASE_BUCKET = "skyhealth"
FILEBASE_ENDPOINT = "https://s3.filebase.com"


def get_doctor_avatar_url(user_id: int) -> str | None:
    """Get doctor avatar URL from Filebase."""
    from api.auth import _get_s3_client

    key = f"avatars/{user_id}.jpg"
    try:
        s3 = _get_s3_client()
        s3.head_object(Bucket=FILEBASE_BUCKET, Key=key)
        return f"{FILEBASE_ENDPOINT}/{FILEBASE_BUCKET}/{key}"
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

    class Config:
        from_attributes = True


class DoctorDetailResponse(DoctorResponse):
    user_id: int | None = None

    class Config:
        from_attributes = True


@router.get("", response_model=List[DoctorResponse])
def list_doctors(
    specialty: Optional[str] = None,
    area: Optional[str] = None,
    online_only: bool = False,
    db: Session = Depends(get_db),
):
    """List all doctors with optional filters.

    Args:
        specialty: Filter by specialty
        area: Filter by area/location
        online_only: If true, only show doctors who are currently online (gig mode)
    """
    query = db.query(Doctor).filter(Doctor.is_available == True)

    if online_only:
        query = query.filter(Doctor.is_online == True)

    if specialty:
        query = query.filter(Doctor.specialty.ilike(f"%{specialty}%"))
    if area:
        query = query.filter(Doctor.area.ilike(f"%{area}%"))

    doctors = query.all()

    # Add effective prices and avatar to each doctor
    result = []
    for doctor in doctors:
        multiplier = doctor.peak_pricing_multiplier or 1.0
        avatar_url = get_doctor_avatar_url(doctor.user_id) if doctor.user_id else None
        doc_dict = {
            "id": doctor.id,
            "name": doctor.name,
            "specialty": doctor.specialty,
            "area": doctor.area,
            "bio": doctor.bio,
            "rating": doctor.rating,
            "review_count": doctor.review_count,
            "consultation_fee": doctor.consultation_fee,
            "is_available": doctor.is_available,
            "hpcsa_number": doctor.hpcsa_number,
            "verification_status": doctor.verification_status,
            "profile_completed": doctor.profile_completed,
            "photo_url": doctor.photo_url,
            "avatar_url": avatar_url,
            "quick_chat_price": doctor.quick_chat_price,
            "video_call_price": doctor.video_call_price,
            "full_consultation_price": doctor.full_consultation_price,
            "prescription_review_price": doctor.prescription_review_price,
            "report_analysis_price": doctor.report_analysis_price,
            "peak_pricing_multiplier": doctor.peak_pricing_multiplier,
            "is_online": doctor.is_online,
        }
        result.append(doc_dict)

    return result


@router.get("/{doctor_id}", response_model=DoctorDetailResponse)
def get_doctor(doctor_id: int, db: Session = Depends(get_db)):
    """Get a specific doctor by ID."""
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found"
        )
    return doctor


@router.get("/search", response_model=List[DoctorResponse])
def search_doctors(q: str, db: Session = Depends(get_db)):
    """Search doctors by name, specialty, or area."""
    doctors = (
        db.query(Doctor)
        .filter(
            Doctor.is_available == True,
            (Doctor.name.ilike(f"%{q}%"))
            | (Doctor.specialty.ilike(f"%{q}%"))
            | (Doctor.area.ilike(f"%{q}%")),
        )
        .all()
    )
    return doctors
