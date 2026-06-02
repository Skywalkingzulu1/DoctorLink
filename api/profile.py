"""
Doctor Profile API endpoints for Doctors on Wheels.
Gig Economy: Custom pricing, service tiers, gig mode toggle
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict

from database import get_db, Doctor, User, Patient
from auth import get_current_user

router = APIRouter(prefix="/api/profile", tags=["profile"])

class PatientProfileUpdate(BaseModel):
    preferred_name: str | None = None
    dob: str | None = None
    gender: str | None = None
    pronouns: str | None = None
    marital_status: str | None = None
    language: str | None = None
    address: str | None = None
    emergency_contact_json: str | None = None
    insurance_json: str | None = None
    pharmacy_json: str | None = None
    referral_json: str | None = None
    medical_history_json: str | None = None
    lifestyle_json: str | None = None
    preventive_json: str | None = None
    mental_health_json: str | None = None

class PatientProfileResponse(BaseModel):
    id: int
    user_id: int
    email: str | None = None
    preferred_name: str | None
    dob: str | None
    gender: str | None
    pronouns: str | None
    marital_status: str | None
    language: str | None
    address: str | None
    emergency_contact_json: str | None
    insurance_json: str | None
    pharmacy_json: str | None
    referral_json: str | None
    medical_history_json: str | None
    lifestyle_json: str | None
    preventive_json: str | None
    mental_health_json: str | None
    created_at: str

    model_config = ConfigDict(from_attributes=True)


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
    practice_number: str | None = None
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
    practice_number: str | None
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

    model_config = ConfigDict(from_attributes=True)


class DoctorPricingResponse(BaseModel):
    quick_chat_price: int
    video_call_price: int
    full_consultation_price: int
    prescription_review_price: int
    report_analysis_price: int
    peak_pricing_multiplier: float
    effective_prices: dict

    model_config = ConfigDict(from_attributes=True)


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
    if request.practice_number is not None:
        doctor.practice_number = request.practice_number
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

@router.get("", response_model=PatientProfileResponse)
@router.get("/patient", response_model=PatientProfileResponse)
def get_my_patient_profile(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Get current patient's profile. Supports both /api/profile and /api/profile/patient."""
    if current_user.role != "PATIENT":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only patients can access this endpoint",
        )

    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if not patient:
        # Create it if it doesn't exist for some reason
        patient = Patient(user_id=current_user.id, preferred_name=current_user.name)
        db.add(patient)
        db.commit()
        db.refresh(patient)

    # Convert created_at to string for response
    patient_dict = {
        "id": patient.id,
        "user_id": patient.user_id,
        "email": current_user.email,
        "preferred_name": patient.preferred_name,
        "dob": patient.dob,
        "gender": patient.gender,
        "pronouns": patient.pronouns,
        "marital_status": patient.marital_status,
        "language": patient.language,
        "address": patient.address,
        "emergency_contact_json": patient.emergency_contact_json,
        "insurance_json": patient.insurance_json,
        "pharmacy_json": patient.pharmacy_json,
        "referral_json": patient.referral_json,
        "medical_history_json": patient.medical_history_json,
        "lifestyle_json": patient.lifestyle_json,
        "preventive_json": patient.preventive_json,
        "mental_health_json": patient.mental_health_json,
        "created_at": patient.created_at.isoformat() if patient.created_at else "",
    }
    return patient_dict

@router.put("/patient", response_model=PatientProfileResponse)
def update_patient_profile(
    request: PatientProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update current patient's profile."""
    if current_user.role != "PATIENT":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only patients can access this endpoint",
        )

    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if not patient:
        patient = Patient(user_id=current_user.id, preferred_name=current_user.name)
        db.add(patient)
    
    # Update fields
    if request.preferred_name is not None: patient.preferred_name = request.preferred_name
    if request.dob is not None: patient.dob = request.dob
    if request.gender is not None: patient.gender = request.gender
    if request.pronouns is not None: patient.pronouns = request.pronouns
    if request.marital_status is not None: patient.marital_status = request.marital_status
    if request.language is not None: patient.language = request.language
    if request.address is not None: patient.address = request.address
    if request.emergency_contact_json is not None: patient.emergency_contact_json = request.emergency_contact_json
    if request.insurance_json is not None: patient.insurance_json = request.insurance_json
    if request.pharmacy_json is not None: patient.pharmacy_json = request.pharmacy_json
    if request.referral_json is not None: patient.referral_json = request.referral_json
    if request.medical_history_json is not None: patient.medical_history_json = request.medical_history_json
    if request.lifestyle_json is not None: patient.lifestyle_json = request.lifestyle_json
    if request.preventive_json is not None: patient.preventive_json = request.preventive_json
    if request.mental_health_json is not None: patient.mental_health_json = request.mental_health_json

    db.commit()
    db.refresh(patient)

    # Convert created_at to string for response
    patient_dict = {
        "id": patient.id,
        "user_id": patient.user_id,
        "email": current_user.email,
        "preferred_name": patient.preferred_name,
        "dob": patient.dob,
        "gender": patient.gender,
        "pronouns": patient.pronouns,
        "marital_status": patient.marital_status,
        "language": patient.language,
        "address": patient.address,
        "emergency_contact_json": patient.emergency_contact_json,
        "insurance_json": patient.insurance_json,
        "pharmacy_json": patient.pharmacy_json,
        "referral_json": patient.referral_json,
        "medical_history_json": patient.medical_history_json,
        "lifestyle_json": patient.lifestyle_json,
        "preventive_json": patient.preventive_json,
        "mental_health_json": patient.mental_health_json,
        "created_at": patient.created_at.isoformat() if patient.created_at else ""
    }
    return patient_dict
