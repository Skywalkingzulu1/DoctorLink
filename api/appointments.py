"""
Appointment API endpoints for DoctorLink.
Gig Economy Model: 20% platform fee, 80% to doctor, tips 100% to doctor
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import (
    get_db,
    Appointment,
    Doctor,
    User,
    AppointmentStatus,
    AppointmentType,
    ServiceTier,
    EscrowStatus,
)
from auth import get_current_user, require_role

router = APIRouter(prefix="/api/appointments", tags=["appointments"])

PLATFORM_FEE_PERCENT = 20

# Filebase config
FILEBASE_BUCKET = "skyhealth"
FILEBASE_ENDPOINT = "https://s3.filebase.com"


def _get_s3_client():
    """Get S3 client."""
    import boto3
    from botocore.config import Config
    import os
    from dotenv import load_dotenv

    load_dotenv()

    return boto3.client(
        "s3",
        endpoint_url=FILEBASE_ENDPOINT,
        aws_access_key_id=os.getenv("FILEBASE_ACCESS_KEY"),
        aws_secret_access_key=os.getenv("FILEBASE_SECRET_KEY"),
        config=Config(region_name="us-east-1", signature_version="s3v4"),
    )


def get_appointment_report_url(appointment_id: int) -> str | None:
    """Get report URL for appointment from Filebase."""
    return f"{FILEBASE_ENDPOINT}/{FILEBASE_BUCKET}/reports/{appointment_id}_report.pdf"


def get_appointment_prescription_url(appointment_id: int) -> str | None:
    """Get prescription URL for appointment from Filebase."""
    return f"{FILEBASE_ENDPOINT}/{FILEBASE_BUCKET}/prescriptions/{appointment_id}.jpg"


def get_appointment_avatar_url(doctor_id: int, db_session) -> str | None:
    """Get doctor avatar URL for appointment."""
    from api.doctors import get_doctor_avatar_url

    doctor = db_session.query(Doctor).filter(Doctor.id == doctor_id).first()
    if doctor and doctor.user_id:
        url = get_doctor_avatar_url(doctor.user_id)
        return url
    return None


def calculate_earnings(base_price: int) -> tuple[int, int]:
    """Calculate platform fee (20%) and doctor earnings (80%)."""
    platform_fee = int(base_price * PLATFORM_FEE_PERCENT / 100)
    doctor_earnings = base_price - platform_fee
    return platform_fee, doctor_earnings


def get_doctor_price_by_tier(doctor: Doctor, tier: ServiceTier) -> int:
    """Get price for a specific service tier from doctor's custom pricing."""
    price_map = {
        ServiceTier.QUICK_CHAT: doctor.quick_chat_price,
        ServiceTier.VIDEO_CALL: doctor.video_call_price,
        ServiceTier.FULL_CONSULTATION: doctor.full_consultation_price,
        ServiceTier.PRESCRIPTION_REVIEW: doctor.prescription_review_price,
        ServiceTier.REPORT_ANALYSIS: doctor.report_analysis_price,
    }
    base_price = price_map.get(tier, doctor.video_call_price)

    # Apply peak pricing if enabled
    if doctor.peak_pricing_multiplier and doctor.peak_pricing_multiplier > 1.0:
        return int(base_price * doctor.peak_pricing_multiplier)

    return base_price


# Pydantic models
class AppointmentResponse(BaseModel):
    id: int
    patient_id: int
    doctor_id: int
    timestamp: datetime
    appointment_type: str
    status: str
    reason: str | None
    price_credits: int | None = None
    service_tier: str | None = None
    base_price: int | None = None
    platform_fee: int | None = None
    doctor_earnings: int | None = None
    escrow_status: str | None = None

    class Config:
        from_attributes = True


class AppointmentDetailResponse(AppointmentResponse):
    patient_name: str | None = None
    doctor_name: str | None = None
    doctor_specialty: str | None = None
    # Filebase URLs for attached files
    report_url: str | None = None
    prescription_url: str | None = None
    avatar_url: str | None = None

    class Config:
        from_attributes = True


class CreateAppointmentRequest(BaseModel):
    doctor_id: int
    timestamp: datetime
    appointment_type: str = "VIDEO"
    service_tier: str = "VIDEO_CALL"
    reason: str | None = None


class UpdateAppointmentRequest(BaseModel):
    status: str | None = None
    notes: str | None = None


@router.get("", response_model=List[AppointmentDetailResponse])
def list_appointments(
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List appointments for the current user."""
    if current_user.role == "PATIENT":
        query = db.query(Appointment).filter(Appointment.patient_id == current_user.id)
    elif current_user.role == "DOCTOR":
        doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
        if not doctor:
            return []
        query = db.query(Appointment).filter(Appointment.doctor_id == doctor.id)
    else:  # ADMIN
        query = db.query(Appointment)

    if status_filter:
        query = query.filter(Appointment.status == status_filter)

    appointments = query.order_by(Appointment.timestamp.desc()).all()

    # Add patient and doctor names + Filebase URLs
    result = []
    for a in appointments:
        patient = db.query(User).filter(User.id == a.patient_id).first()
        doctor = db.query(Doctor).filter(Doctor.id == a.doctor_id).first()

        # Calculate earnings display
        total_cost = a.base_price or a.price_credits or 0
        platform_fee = a.platform_fee or int(total_cost * PLATFORM_FEE_PERCENT / 100)
        doctor_earnings = a.doctor_earnings or (total_cost - platform_fee)

        # Get Filebase URLs
        report_url = get_appointment_report_url(a.id)
        prescription_url = get_appointment_prescription_url(a.id)
        avatar_url = get_appointment_avatar_url(a.doctor_id, db) if doctor else None

        result.append(
            {
                "id": a.id,
                "patient_id": a.patient_id,
                "doctor_id": a.doctor_id,
                "timestamp": a.timestamp.isoformat() if a.timestamp else None,
                "appointment_type": a.appointment_type.value
                if a.appointment_type
                else "VIDEO",
                "status": a.status.value if a.status else "SCHEDULED",
                "reason": a.reason,
                "price_credits": a.price_credits,
                "service_tier": a.service_tier.value
                if a.service_tier
                else "VIDEO_CALL",
                "base_price": a.base_price or total_cost,
                "platform_fee": platform_fee,
                "doctor_earnings": doctor_earnings,
                "escrow_status": a.escrow_status.value
                if a.escrow_status
                else "PENDING",
                "patient_name": patient.name if patient else None,
                "doctor_name": doctor.name if doctor else None,
                "doctor_specialty": doctor.specialty if doctor else None,
                "report_url": report_url,
                "prescription_url": prescription_url,
                "avatar_url": avatar_url,
            }
        )

    return result


@router.post(
    "", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED
)
def create_appointment(
    request: CreateAppointmentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new appointment with gig economy pricing (20% platform fee)."""
    try:
        # Verify doctor exists
        doctor = db.query(Doctor).filter(Doctor.id == request.doctor_id).first()
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found"
            )

        # Check if doctor is online (gig mode)
        if doctor.is_online is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Doctor is currently offline. Please try again later.",
            )

        # Get price based on service tier
        try:
            tier = ServiceTier(request.service_tier)
        except ValueError:
            tier = ServiceTier.VIDEO_CALL

        base_price = get_doctor_price_by_tier(doctor, tier)

        # Apply inconvenience discount if active
        final_price = base_price
        if (
            current_user.inconvenience_discount_active
            and current_user.inconvenience_discount_amount > 0
        ):
            discount = min(current_user.inconvenience_discount_amount, base_price)
            final_price = base_price - discount

        # Check credits
        if current_user.credits < final_price:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient credits. Need {final_price} credits.",
            )

        # Calculate earnings split
        platform_fee, doctor_earnings = calculate_earnings(base_price)

        # Create appointment with gig economy fields
        appointment = Appointment(
            patient_id=current_user.id,
            doctor_id=request.doctor_id,
            timestamp=request.timestamp,
            appointment_type=AppointmentType(request.appointment_type),
            reason=request.reason,
            status=AppointmentStatus.SCHEDULED,
            price_credits=final_price,
            service_tier=tier,
            base_price=base_price,
            platform_fee=platform_fee,
            doctor_earnings=doctor_earnings,
            escrow_status=EscrowStatus.PENDING,
        )
        db.add(appointment)

        # Deduct credits from patient
        current_user.credits -= final_price

        # Clear inconvenience discount after use
        if current_user.inconvenience_discount_active:
            current_user.inconvenience_discount_active = False
            current_user.inconvenience_discount_amount = 0
            current_user.inconvenience_discount_reason = None

        db.commit()
        db.refresh(appointment)

        return appointment
    except Exception as e:
        import traceback

        print(f"ERROR creating appointment: {e}")
        print(traceback.format_exc())
        raise


@router.get("/{appointment_id}", response_model=AppointmentDetailResponse)
def get_appointment(
    appointment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific appointment."""
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found"
        )

    # Check access
    if current_user.role == "PATIENT" and appointment.patient_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
        )

    if current_user.role == "DOCTOR":
        doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
        if not doctor or appointment.doctor_id != doctor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )

    patient = db.query(User).filter(User.id == appointment.patient_id).first()
    doctor = db.query(Doctor).filter(Doctor.id == appointment.doctor_id).first()

    # Get Filebase URLs
    report_url = get_appointment_report_url(appointment.id)
    prescription_url = get_appointment_prescription_url(appointment.id)
    avatar_url = (
        get_appointment_avatar_url(appointment.doctor_id, db) if doctor else None
    )

    return {
        "id": appointment.id,
        "patient_id": appointment.patient_id,
        "doctor_id": appointment.doctor_id,
        "timestamp": appointment.timestamp.isoformat()
        if appointment.timestamp
        else None,
        "appointment_type": appointment.appointment_type.value
        if appointment.appointment_type
        else "VIDEO",
        "status": appointment.status.value if appointment.status else "SCHEDULED",
        "reason": appointment.reason,
        "price_credits": appointment.price_credits,
        "service_tier": appointment.service_tier.value
        if appointment.service_tier
        else "VIDEO_CALL",
        "base_price": appointment.base_price,
        "platform_fee": appointment.platform_fee,
        "doctor_earnings": appointment.doctor_earnings,
        "escrow_status": appointment.escrow_status.value
        if appointment.escrow_status
        else "PENDING",
        "patient_name": patient.name if patient else None,
        "doctor_name": doctor.name if doctor else None,
        "doctor_specialty": doctor.specialty if doctor else None,
        "report_url": report_url,
        "prescription_url": prescription_url,
        "avatar_url": avatar_url,
    }


@router.patch("/{appointment_id}", response_model=AppointmentResponse)
def update_appointment(
    appointment_id: int,
    request: UpdateAppointmentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update an appointment (accept/reject/complete) with escrow logic."""
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found"
        )

    # Only doctor or admin can update status
    if current_user.role == "PATIENT":
        if appointment.patient_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )
        # Patients can only cancel
        if request.status and request.status != "CANCELLED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot change status"
            )

    if request.status:
        try:
            appointment.status = AppointmentStatus(request.status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status"
            )

        # Handle status changes with escrow logic
        if request.status == "ACTIVE":
            # Call started - move to HELD
            appointment.escrow_status = EscrowStatus.HELD
            appointment.started_at = datetime.utcnow()

        elif request.status == "COMPLETED":
            # Call completed - release escrow to doctor
            appointment.escrow_status = EscrowStatus.RELEASED
            appointment.ended_at = datetime.utcnow()

            # Calculate duration
            if appointment.started_at:
                duration = (
                    appointment.ended_at - appointment.started_at
                ).total_seconds() / 60
                appointment.duration_minutes = int(duration)

            # Add earnings to doctor (base price + any tips)
            doctor = db.query(Doctor).filter(Doctor.id == appointment.doctor_id).first()
            if doctor and appointment.doctor_earnings:
                total_earnings = appointment.doctor_earnings + (
                    appointment.tip_amount or 0
                )
                doctor.pending_earnings = (
                    doctor.pending_earnings or 0
                ) + total_earnings
                doctor.total_earnings = (doctor.total_earnings or 0) + total_earnings

    if request.notes:
        appointment.notes = request.notes

    db.commit()
    db.refresh(appointment)

    return appointment


@router.delete("/{appointment_id}")
def cancel_appointment(
    appointment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cancel an appointment - refund patient via escrow."""
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found"
        )

    # Check ownership
    if current_user.role == "PATIENT" and appointment.patient_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
        )

    if current_user.role == "DOCTOR":
        doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
        if not doctor or appointment.doctor_id != doctor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )

    # Refund credits if not already completed - release from escrow
    if (
        appointment.status != AppointmentStatus.COMPLETED
        and appointment.status != AppointmentStatus.CANCELLED
        and appointment.escrow_status != EscrowStatus.REFUNDED
    ):
        patient = db.query(User).filter(User.id == appointment.patient_id).first()
        if patient:
            refund_amount = appointment.price_credits or appointment.base_price or 150
            patient.credits += refund_amount

        # Mark escrow as refunded
        appointment.escrow_status = EscrowStatus.REFUNDED

    appointment.status = AppointmentStatus.CANCELLED
    db.commit()

    return {"message": "Appointment cancelled, credits refunded"}


@router.post("/{appointment_id}/report-issue")
def report_issue(
    appointment_id: int,
    issue_type: str = "video_quality",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Report an issue to get inconvenience discount on next booking."""
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    # Only the patient who booked can report issues
    if appointment.patient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Calculate 10% discount of the base price
    base_price = appointment.base_price or appointment.price_credits or 150
    discount_amount = int(base_price * 0.10)

    # Apply to user for next booking
    current_user.inconvenience_discount_active = True
    current_user.inconvenience_discount_amount = discount_amount
    current_user.inconvenience_discount_reason = issue_type

    db.commit()

    return {
        "message": "Issue reported. 10% discount applied to your next booking.",
        "discount_amount": discount_amount,
        "reason": issue_type,
    }


@router.get("/{appointment_id}/pricing")
def get_appointment_pricing(
    appointment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get detailed pricing breakdown for an appointment."""
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    doctor = db.query(Doctor).filter(Doctor.id == appointment.doctor_id).first()

    base_price = appointment.base_price or appointment.price_credits or 150
    platform_fee = appointment.platform_fee or int(base_price * 0.20)
    doctor_share = base_price - platform_fee
    tip = appointment.tip_amount or 0

    return {
        "appointment_id": appointment_id,
        "service_tier": appointment.service_tier.value
        if appointment.service_tier
        else "VIDEO_CALL",
        "base_price": base_price,
        "platform_fee": platform_fee,  # 20%
        "doctor_share": doctor_share,  # 80%
        "tip_amount": tip,  # 100% to doctor
        "total_to_doctor": doctor_share + tip,
        "escrow_status": appointment.escrow_status.value
        if appointment.escrow_status
        else "PENDING",
    }
