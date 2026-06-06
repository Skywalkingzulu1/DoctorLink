"""
Appointment API endpoints for Doctors on Wheels.
Gig Economy Model: 20% platform fee, 80% to doctor, tips 100% to doctor.
Integrated with Somnia Agentic L1 for on-chain escrow and AI-powered features.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import List, Optional
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict

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
from api.storage import get_public_url, get_presigned_url, object_exists
from somnia.wallet import ensure_user_wallet, get_user_wallet
from somnia.agent_service import transfer_t800_to_user
from api.somnia_agent import run_all_triage_tools
import json

router = APIRouter(prefix="/api/appointments", tags=["appointments"])

PLATFORM_FEE_PERCENT = 20


def get_appointment_report_url(appointment_id: int) -> str | None:
    """Get report URL for appointment from Filebase."""
    key = f"reports/{appointment_id}_report.pdf"
    if object_exists(key):
        return get_presigned_url(key)
    return None


def get_appointment_prescription_url(appointment_id: int) -> str | None:
    """Get prescription URL for appointment from Filebase."""
    key = f"prescriptions/{appointment_id}.jpg"
    if object_exists(key):
        return get_presigned_url(key)
    return None


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
    location: str | None = None
    price_credits: int | None = None
    service_tier: str | None = None
    base_price: int | None = None
    platform_fee: int | None = None
    doctor_earnings: int | None = None
    escrow_status: str | None = None
    triage_data: str | None = None
    triage_tools_results: str | None = None

    model_config = ConfigDict(from_attributes=True)


class AppointmentDetailResponse(AppointmentResponse):
    patient_name: str | None = None
    doctor_name: str | None = None
    doctor_specialty: str | None = None
    # Filebase URLs for attached files
    report_url: str | None = None
    prescription_url: str | None = None
    avatar_url: str | None = None

    model_config = ConfigDict(from_attributes=True)


class CreateAppointmentRequest(BaseModel):
    doctor_id: int
    timestamp: datetime
    appointment_type: str = "VIDEO"
    service_tier: str = "VIDEO_CALL"
    reason: str | None = None
    location: str | None = None
    triage_data: str | None = None  # JSON string from client
    payment_method: str = "credits"  # credits, yoco, somnia, t800


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
                "location": a.location,
                "triage_data": a.triage_data,
                "triage_tools_results": a.triage_tools_results,
            }
        )

    return result


@router.post(
    "", response_model=AppointmentResponse, status_code=status.HTTP_200_OK
)
async def create_appointment(
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

        # Check credits - Bypass if using fiat (Yoco) or on-chain STT
        if request.payment_method == "credits":
            if current_user.credits < final_price:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Insufficient credits. Need {final_price} credits. Try paying with Yoco.",
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
            location=request.location,
            status=AppointmentStatus.SCHEDULED,
            price_credits=final_price,
            service_tier=tier,
            base_price=base_price,
            platform_fee=platform_fee,
            doctor_earnings=doctor_earnings,
            escrow_status=EscrowStatus.PENDING,
            triage_data=request.triage_data,
            payment_method=request.payment_method,
        )
        db.add(appointment)
        
        # Only deduct credits and clear discounts if paying with credits
        if request.payment_method == "credits":
            # Deduct credits from patient
            current_user.credits -= final_price

            # Clear inconvenience discount after use
            if current_user.inconvenience_discount_active:
                current_user.inconvenience_discount_active = False
                current_user.inconvenience_discount_amount = 0
                current_user.inconvenience_discount_reason = None

            # Ensure user changes are tracked in this session
            db.merge(current_user)
        
        db.commit()  # Persist everything
        db.refresh(appointment)  # Load generated ID

        # Run 10 Specialized AI Triage & Noting Tools
        if request.triage_data:
            try:
                results = await run_all_triage_tools(request.triage_data)
                appointment.triage_tools_results = json.dumps(results)
                db.commit() # Save AI results
            except Exception as e:
                print(f"AI Triage tools failed: {e}")

        # Send T800 reward automatically on booking (1 T800 = R1.00)
        try:
            patient_wallet = ensure_user_wallet(current_user.id)
            if patient_wallet and patient_wallet.get("address"):
                # Transfer amount equal to the base price in Rands
                reward_amount = float(base_price)
                transfer_t800_to_user(patient_wallet["address"], reward_amount)
        except Exception as e:
            print(f"[Somnia] T800 reward transfer failed: {e}")

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
            appointment.started_at = datetime.now(timezone.utc)

        elif request.status == "COMPLETED":
            # Call completed - release escrow to doctor
            appointment.escrow_status = EscrowStatus.RELEASED
            appointment.ended_at = datetime.now(timezone.utc)

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


@router.post("/{appointment_id}/pay-with-somnia")
def pay_with_somnia(
    appointment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Pay for an appointment using Somnia STT tokens via on-chain escrow."""
    appointment = (
        db.query(Appointment).filter(Appointment.id == appointment_id).first()
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if appointment.patient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your appointment")

    from somnia.wallet import get_user_wallet, ensure_user_wallet, get_user_balance
    from somnia.escrow_service import deposit_escrow
    from somnia.client import somnia

    ensure_user_wallet(current_user.id)
    patient_wallet = get_user_wallet(current_user.id)

    doctor = db.query(Doctor).filter(Doctor.id == appointment.doctor_id).first()
    if not doctor or not doctor.user_id:
        raise HTTPException(status_code=400, detail="Doctor has no linked user account")
    doctor_wallet = get_user_wallet(doctor.user_id)
    if not doctor_wallet:
        doctor_wallet = ensure_user_wallet(doctor.user_id)

    amount = (appointment.base_price or appointment.price_credits or 150) * 10**18

    # Check balance before deposit
    balance = somnia.get_balance(patient_wallet["address"])
    if balance < amount:
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient STT balance. Have {somnia.w3.from_wei(balance, 'ether'):.4f} STT, need {somnia.w3.from_wei(amount, 'ether'):.4f} STT",
        )

    result = deposit_escrow(appointment_id, doctor_wallet["address"], amount)

    appointment.escrow_status = EscrowStatus.HELD
    appointment.somnia_tx_hash = result["tx_hash"]
    db.commit()

    return {
        "message": "Payment deposited to Somnia escrow",
        "tx_hash": result["tx_hash"],
        "appointment_id": appointment_id,
    }


PLATFORM_FEE_PERCENT = 20

def _get_platform_account(db: Session) -> User:
    """Find or create the platform fee holding account."""
    platform = db.query(User).filter(User.email == "platform@doctorlink.co.za").first()
    if not platform:
        from auth import hash_password
        platform = User(
            name="Doctors on Wheels Platform",
            email="platform@doctorlink.co.za",
            password_hash=hash_password("platform-admin-2026"),
            role="PATIENT",
            credits=0,
            t800_balance=0,
            email_verified=True,
        )
        db.add(platform)
        db.flush()
    return platform


@router.post("/{appointment_id}/pay-with-t800")
def pay_with_t800(
    appointment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Pay for an appointment using off-chain T800 balance. 80% to doctor, 20% to platform."""
    patient = db.query(User).filter(User.id == current_user.id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    appointment = (
        db.query(Appointment).filter(Appointment.id == appointment_id).first()
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if appointment.patient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your appointment")

    doctor = db.query(Doctor).filter(Doctor.id == appointment.doctor_id).first()
    if not doctor or not doctor.user_id:
        raise HTTPException(status_code=400, detail="Doctor has no linked user account")
    doctor_user = db.query(User).filter(User.id == doctor.user_id).first()
    if not doctor_user:
        raise HTTPException(status_code=400, detail="Doctor user account not found")

    amount_credits = appointment.base_price or appointment.price_credits or 150
    cost_t800 = amount_credits * 10  # 1 credit = 10 T800
    platform_fee_t800 = cost_t800 * PLATFORM_FEE_PERCENT // 100  # 20%
    doctor_earnings_t800 = cost_t800 - platform_fee_t800

    if (patient.t800_balance or 0) < cost_t800:
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient T800. Have {patient.t800_balance or 0:.0f} T800, need {cost_t800} T800",
        )

    platform_acct = _get_platform_account(db)

    patient.t800_balance = (patient.t800_balance or 0) - cost_t800
    doctor_user.t800_balance = (doctor_user.t800_balance or 0) + doctor_earnings_t800
    platform_acct.t800_balance = (platform_acct.t800_balance or 0) + platform_fee_t800

    appointment.payment_method = "t800"
    appointment.escrow_status = EscrowStatus.RELEASED
    appointment.platform_fee_t800 = platform_fee_t800
    db.commit()

    return {
        "message": "Payment sent via T800 tokens",
        "amount_t800": cost_t800,
        "doctor_share_t800": doctor_earnings_t800,
        "platform_fee_t800": platform_fee_t800,
        "new_balance": patient.t800_balance,
        "appointment_id": appointment_id,
    }


@router.post("/{appointment_id}/complete")
def complete_appointment(
    appointment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark appointment as COMPLETED and release escrow/credits to doctor."""
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    # Only doctor or patient can complete (usually doctor)
    doctor_obj = db.query(Doctor).filter(Doctor.id == appointment.doctor_id).first()
    is_doctor = doctor_obj and doctor_obj.user_id == current_user.id
    is_patient = appointment.patient_id == current_user.id

    if not is_doctor and not is_patient:
        raise HTTPException(status_code=403, detail="Access denied")

    if appointment.status == AppointmentStatus.COMPLETED:
        return {"message": "Already completed"}

    appointment.status = AppointmentStatus.COMPLETED
    appointment.ended_at = datetime.now(timezone.utc)
    if appointment.started_at:
        duration = (appointment.ended_at - appointment.started_at).total_seconds() / 60
        appointment.duration_minutes = int(duration)

    # 1. Handle Somnia Escrow Release
    if appointment.escrow_status == EscrowStatus.HELD and appointment.somnia_tx_hash:
        try:
            from somnia.escrow_service import release_escrow
            release_result = release_escrow(appointment_id)
            appointment.escrow_status = EscrowStatus.RELEASED
            appointment.somnia_release_tx = release_result["tx_hash"]
            print(f"DEBUG: On-chain escrow released for appt {appointment_id}")
        except Exception as e:
            print(f"ERROR: Failed to release on-chain escrow: {e}")

    # 2. Handle Credits Transfer
    if not appointment.somnia_tx_hash and appointment.payment_method != "t800":
        if doctor_obj and doctor_obj.user_id:
            doctor_user = db.query(User).filter(User.id == doctor_obj.user_id).first()
            if doctor_user:
                earnings = appointment.doctor_earnings or int(
                    (appointment.price_credits or 150) * 0.8
                )
                doctor_user.credits = (doctor_user.credits or 0) + earnings
                print(f"DEBUG: Transferred {earnings} credits to doctor {doctor_user.id}")

    db.commit()
    return {"message": "Appointment completed and payment processed"}


@router.get("/{appointment_id}/somnia-status")
def get_somnia_status(
    appointment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get on-chain status for an appointment."""
    appointment = (
        db.query(Appointment).filter(Appointment.id == appointment_id).first()
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    return {
        "appointment_id": appointment_id,
        "escrow_status": appointment.escrow_status.value
        if appointment.escrow_status
        else "PENDING",
        "somnia_tx_hash": appointment.somnia_tx_hash,
        "somnia_release_tx": appointment.somnia_release_tx,
        "somnia_refund_tx": appointment.somnia_refund_tx,
        "agent_results": appointment.somnia_agent_results,
    }


@router.post("/{appointment_id}/questionnaire")
def update_appointment_questionnaire(
    appointment_id: int,
    data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update appointment triage data with additional questionnaire answers."""
    appointment = (
        db.query(Appointment).filter(Appointment.id == appointment_id).first()
    )
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found"
        )
    
    # Verify ownership (patient)
    if appointment.patient_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
        )
    
    # Merge existing triage_data with new questionnaire data
    try:
        current_triage = {}
        if appointment.triage_data:
            current_triage = json.loads(appointment.triage_data)
        
        current_triage["questionnaire"] = data
        appointment.triage_data = json.dumps(current_triage)
        db.commit()
        return {"message": "Questionnaire submitted successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
