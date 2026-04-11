"""
Prescription API endpoints for DoctorLink.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db, Prescription, Appointment, Doctor, User
from auth import get_current_user, require_role

router = APIRouter(prefix="/api/prescriptions", tags=["prescriptions"])


class PrescriptionResponse(BaseModel):
    id: int
    appointment_id: int
    patient_id: int
    doctor_id: int
    medication: str
    dosage: str
    instructions: str | None

    class Config:
        from_attributes = True


class CreatePrescriptionRequest(BaseModel):
    appointment_id: int
    medication: str
    dosage: str
    instructions: str | None = None


@router.get("", response_model=List[PrescriptionResponse])
def list_prescriptions(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """List prescriptions for the current user."""
    if current_user.role == "PATIENT":
        prescriptions = (
            db.query(Prescription)
            .filter(Prescription.patient_id == current_user.id)
            .all()
        )
    elif current_user.role == "DOCTOR":
        doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
        if not doctor:
            return []
        prescriptions = (
            db.query(Prescription).filter(Prescription.doctor_id == doctor.id).all()
        )
    else:
        prescriptions = db.query(Prescription).all()

    return prescriptions


@router.post(
    "", response_model=PrescriptionResponse, status_code=status.HTTP_201_CREATED
)
def create_prescription(
    request: CreatePrescriptionRequest,
    current_user: User = Depends(require_role(["DOCTOR"])),
    db: Session = Depends(get_db),
):
    """Create a prescription (doctor only)."""
    # Verify doctor
    doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Doctor profile not found"
        )

    # Verify appointment
    appointment = (
        db.query(Appointment).filter(Appointment.id == request.appointment_id).first()
    )
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found"
        )

    # Create prescription
    prescription = Prescription(
        appointment_id=request.appointment_id,
        patient_id=appointment.patient_id,
        doctor_id=doctor.id,
        medication=request.medication,
        dosage=request.dosage,
        instructions=request.instructions,
    )
    db.add(prescription)
    db.commit()
    db.refresh(prescription)

    return prescription


@router.get("/{prescription_id}", response_model=PrescriptionResponse)
def get_prescription(
    prescription_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific prescription."""
    prescription = (
        db.query(Prescription).filter(Prescription.id == prescription_id).first()
    )
    if not prescription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Prescription not found"
        )

    # Check access
    if current_user.role == "PATIENT" and prescription.patient_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
        )

    return prescription
