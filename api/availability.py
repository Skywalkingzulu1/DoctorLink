"""
Doctor Availability API for DoctorLink.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, validator

from database import get_db, Doctor, User, DoctorSchedule, TimeSlot
from auth import get_current_user

router = APIRouter(prefix="/api/availability", tags=["availability"])


class ScheduleCreate(BaseModel):
    day_of_week: int
    start_time: str
    end_time: str

    @validator("day_of_week")
    def validate_day(cls, v):
        if not 0 <= v <= 6:
            raise ValueError("Day must be 0-6 (Monday-Sunday)")
        return v

    @validator("start_time")
    def validate_time(cls, v):
        if len(v) != 5 or v[2] != ":":
            raise ValueError("Time must be HH:MM format")
        return v


class ScheduleResponse(BaseModel):
    id: int
    day_of_week: int
    start_time: str
    end_time: str
    is_active: bool

    class Config:
        from_attributes = True


class TimeSlotResponse(BaseModel):
    id: int
    date: str
    start_time: str
    end_time: str
    is_booked: bool


@router.get("/doctor", response_model=list[ScheduleResponse])
def get_doctor_schedule(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Get current doctor's schedule."""
    if current_user.role != "DOCTOR":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only doctors can access schedule",
        )

    doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Doctor profile not found"
        )

    schedules = (
        db.query(DoctorSchedule)
        .filter(DoctorSchedule.doctor_id == doctor.id, DoctorSchedule.is_active == True)
        .all()
    )

    return schedules


@router.post("/doctor/schedule", response_model=ScheduleResponse)
def add_schedule(
    schedule: ScheduleCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add time slot to doctor's schedule."""
    if current_user.role != "DOCTOR":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only doctors can manage schedule",
        )

    doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Doctor profile not found"
        )

    # Check for overlapping schedules
    existing = (
        db.query(DoctorSchedule)
        .filter(
            DoctorSchedule.doctor_id == doctor.id,
            DoctorSchedule.day_of_week == schedule.day_of_week,
            DoctorSchedule.is_active == True,
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Schedule already exists for day {schedule.day_of_week}. Update or delete existing first.",
        )

    new_schedule = DoctorSchedule(
        doctor_id=doctor.id,
        day_of_week=schedule.day_of_week,
        start_time=schedule.start_time,
        end_time=schedule.end_time,
        is_active=True,
    )
    db.add(new_schedule)
    db.commit()
    db.refresh(new_schedule)

    return new_schedule


@router.delete("/doctor/schedule/{schedule_id}")
def delete_schedule(
    schedule_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a schedule slot."""
    if current_user.role != "DOCTOR":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only doctors can manage schedule",
        )

    doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Doctor profile not found"
        )

    schedule = (
        db.query(DoctorSchedule)
        .filter(DoctorSchedule.id == schedule_id, DoctorSchedule.doctor_id == doctor.id)
        .first()
    )

    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found"
        )

    schedule.is_active = False
    db.commit()

    return {"message": "Schedule deleted"}


@router.get("/doctor/{doctor_id}/slots")
def get_available_slots(
    doctor_id: int,
    start_date: str = None,
    end_date: str = None,
    db: Session = Depends(get_db),
):
    """Get available time slots for a doctor."""
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found"
        )

    # Parse dates
    if start_date:
        start = date.fromisoformat(start_date)
    else:
        start = date.today()

    if end_date:
        end = date.fromisoformat(end_date)
    else:
        end = start + timedelta(days=7)

    # Get doctor's schedule
    schedules = (
        db.query(DoctorSchedule)
        .filter(DoctorSchedule.doctor_id == doctor_id, DoctorSchedule.is_active == True)
        .all()
    )

    # Generate slots
    available_slots = []
    current = start
    while current <= end:
        day_of_week = current.weekday()

        # Find schedule for this day
        day_schedule = [s for s in schedules if s.day_of_week == day_of_week]

        if day_schedule:
            for schedule in day_schedule:
                # Generate hourly slots
                start_hour = int(schedule.start_time.split(":")[0])
                end_hour = int(schedule.end_time.split(":")[0])

                for hour in range(start_hour, end_hour):
                    slot_time = f"{hour:02d}:00"

                    # Check if slot is already booked
                    existing = (
                        db.query(TimeSlot)
                        .filter(
                            TimeSlot.doctor_id == doctor_id,
                            TimeSlot.date == current,
                            TimeSlot.start_time == slot_time,
                            TimeSlot.is_booked == True,
                        )
                        .first()
                    )

                    if not existing:
                        available_slots.append(
                            {
                                "date": current.isoformat(),
                                "time": slot_time,
                                "available": True,
                            }
                        )

        current += timedelta(days=1)

    return available_slots
