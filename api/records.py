"""
Medical Records API endpoints for DoctorLink.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict

from database import get_db, MedicalRecord, Appointment, Doctor, User
from auth import get_current_user

router = APIRouter(prefix="/api/records", tags=["medical_records"])


class MedicalRecordResponse(BaseModel):
    id: int
    patient_id: int
    doctor_id: int
    appointment_id: int | None
    summary: str
    diagnosis: str | None
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class CreateRecordRequest(BaseModel):
    appointment_id: int | None = None
    summary: str
    diagnosis: str | None = None


@router.get("", response_model=List[MedicalRecordResponse])
def list_records(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """List medical records for the current user."""
    if current_user.role == "PATIENT":
        records = (
            db.query(MedicalRecord)
            .filter(MedicalRecord.patient_id == current_user.id)
            .all()
        )
    elif current_user.role == "DOCTOR":
        doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
        if not doctor:
            return []
        records = (
            db.query(MedicalRecord).filter(MedicalRecord.doctor_id == doctor.id).all()
        )
    else:
        records = db.query(MedicalRecord).all()

    return [
        {
            "created_at": r.created_at.isoformat() if r.created_at else "",
            **MedicalRecord.model_validate(r).model_dump(),
        }
        for r in records
    ]


@router.post(
    "", response_model=MedicalRecordResponse, status_code=status.HTTP_201_CREATED
)
def create_record(
    request: CreateRecordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a medical record (doctor only)."""
    if current_user.role != "DOCTOR":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Doctors only"
        )

    doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Doctor profile not found"
        )

    # Determine patient from appointment or use provided patient_id
    patient_id = None
    if request.appointment_id:
        appointment = (
            db.query(Appointment)
            .filter(Appointment.id == request.appointment_id)
            .first()
        )
        if appointment:
            patient_id = appointment.patient_id

    if not patient_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Patient not specified"
        )

    record = MedicalRecord(
        patient_id=patient_id,
        doctor_id=doctor.id,
        appointment_id=request.appointment_id,
        summary=request.summary,
        diagnosis=request.diagnosis,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return {
        "created_at": record.created_at.isoformat() if record.created_at else "",
        **MedicalRecord.model_validate(record).model_dump(),
    }
