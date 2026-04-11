"""
Waiting Room API for DoctorLink.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from database import get_db, Doctor, User, Appointment
from auth import get_current_user

router = APIRouter(prefix="/api/waiting-room", tags=["waiting-room"])


class WaitingRoomResponse(BaseModel):
    appointment_id: int
    patient_id: int
    patient_name: str
    doctor_id: int
    appointment_time: str
    joined_at: Optional[str] = None
    position: int


@router.get("")
def get_waiting_room(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Get waiting room for doctor's appointments."""
    if current_user.role != "DOCTOR":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only doctors can view waiting room",
        )

    doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Doctor profile not found"
        )

    # Get appointments that are SCHEDULED and at or past their time
    now = datetime.utcnow()
    appointments = (
        db.query(Appointment)
        .filter(
            Appointment.doctor_id == doctor.id,
            Appointment.status == "SCHEDULED",
            Appointment.timestamp <= now,
        )
        .order_by(Appointment.timestamp.asc())
        .all()
    )

    waiting = []
    for i, appt in enumerate(appointments):
        patient = db.query(User).filter(User.id == appt.patient_id).first()
        waiting.append(
            {
                "appointment_id": appt.id,
                "patient_id": appt.patient_id,
                "patient_name": patient.name if patient else "Unknown",
                "doctor_id": appt.doctor_id,
                "appointment_time": appt.timestamp.isoformat()
                if appt.timestamp
                else None,
                "reason": appt.reason,
                "position": i + 1,
            }
        )

    return waiting


@router.post("/join/{appointment_id}")
def join_waiting_room(
    appointment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Patient joins waiting room for their appointment."""
    appointment = (
        db.query(Appointment)
        .filter(
            Appointment.id == appointment_id, Appointment.patient_id == current_user.id
        )
        .first()
    )

    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found"
        )

    if appointment.status != "SCHEDULED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Appointment is not in scheduled state",
        )

    # Check if appointment time has arrived or passed
    now = datetime.utcnow()
    if appointment.timestamp > now:
        wait_seconds = (appointment.timestamp - now).total_seconds()
        minutes_until = int(wait_seconds / 60)
        return {
            "message": f"Appointment starts in {minutes_until} minutes",
            "waiting": False,
            "appointment_time": appointment.timestamp.isoformat(),
        }

    # Update teleconsultation status
    appointment.teleconsultation_status = "waiting"
    db.commit()

    # Get position in queue
    doctor_appointments = (
        db.query(Appointment)
        .filter(
            Appointment.doctor_id == appointment.doctor_id,
            Appointment.status == "SCHEDULED",
            Appointment.teleconsultation_status == "waiting",
            Appointment.timestamp <= now,
        )
        .all()
    )

    position = sum(1 for a in doctor_appointments if a.id <= appointment.id)

    return {
        "message": "Joined waiting room",
        "waiting": True,
        "position": position,
        "appointment_time": appointment.timestamp.isoformat(),
    }


@router.post("/admit/{appointment_id}")
def admit_patient(
    appointment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Doctor admits patient from waiting room to video call."""
    if current_user.role != "DOCTOR":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only doctors can admit patients",
        )

    doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Doctor profile not found"
        )

    appointment = (
        db.query(Appointment)
        .filter(Appointment.id == appointment_id, Appointment.doctor_id == doctor.id)
        .first()
    )

    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found"
        )

    # Update to ACTIVE
    appointment.status = "ACTIVE"
    appointment.teleconsultation_status = "active"
    db.commit()

    return {
        "message": "Patient admitted to video call",
        "appointment_id": appointment_id,
        "status": "ACTIVE",
    }


@router.post("/leave/{appointment_id}")
def leave_waiting_room(
    appointment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Patient leaves waiting room."""
    appointment = (
        db.query(Appointment)
        .filter(
            Appointment.id == appointment_id, Appointment.patient_id == current_user.id
        )
        .first()
    )

    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found"
        )

    if appointment.teleconsultation_status == "waiting":
        appointment.teleconsultation_status = "left"
        db.commit()

    return {"message": "Left waiting room"}
