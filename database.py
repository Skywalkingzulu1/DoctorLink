"""
SQLite database configuration and models for DoctorLink.
"""

import os
from datetime import datetime, date, timedelta
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    DateTime,
    Date,
    ForeignKey,
    Text,
    Enum as SQLEnum,
    Float,
    Boolean,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from enum import Enum

from config import settings

# Database path
DATABASE_URL = settings.DATABASE_URL

# Create engine
# If it's a sqlite database, we need the check_same_thread=False argument
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL, connect_args={"check_same_thread": False}, echo=False
    )
else:
    engine = create_engine(DATABASE_URL, echo=False)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class
Base = declarative_base()


# Enums
class UserRole(str, Enum):
    PATIENT = "PATIENT"
    DOCTOR = "DOCTOR"
    ADMIN = "ADMIN"


class AppointmentStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class AppointmentType(str, Enum):
    VIDEO = "VIDEO"
    INPERSON = "INPERSON"
    FOLLOWUP = "FOLLOWUP"


class ServiceTier(str, Enum):
    QUICK_CHAT = "QUICK_CHAT"  # 10 min - default 50 credits
    VIDEO_CALL = "VIDEO_CALL"  # 30 min - default 150 credits
    FULL_CONSULTATION = "FULL_CONSULTATION"  # 60 min - default 250 credits
    PRESCRIPTION_REVIEW = "PRESCRIPTION_REVIEW"  # Report analysis - default 80 credits
    REPORT_ANALYSIS = "REPORT_ANALYSIS"  # Medical report review - default 120 credits


class EscrowStatus(str, Enum):
    PENDING = "PENDING"  # Payment collected, awaiting call
    HELD = "HELD"  # Call in progress
    RELEASED = "RELEASED"  # Call complete, doctor paid
    REFUNDED = "REFUNDED"  # Cancelled/no-show, patient refunded


class RoomStatus(str, Enum):
    WAITING = "WAITING"
    LIVE = "LIVE"
    ENDED = "ENDED"


# Models
class User(Base):
    __tablename__ = "Profiles"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=True) # Allow null for Supabase-only users
    name = Column(String, nullable=False)
    role = Column(String, nullable=False, default="PATIENT")
    phone = Column(String, nullable=True)
    credits = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime, nullable=True)

    # Verification
    email_verified = Column(Boolean, default=False)
    phone_verified = Column(Boolean, default=False)
    verification_level = Column(String, default="none")  # none, basic, verified

    # Hashgraph
    hashgraph_account_id = Column(String, nullable=True)

    # Inconvenience Discount
    inconvenience_discount_amount = Column(Integer, default=0)
    inconvenience_discount_active = Column(Boolean, default=False)
    inconvenience_discount_reason = Column(String, nullable=True)

    # Relationships
    appointments = relationship(
        "Appointment", back_populates="patient", foreign_keys="Appointment.patient_id"
    )
    prescriptions = relationship("Prescription", back_populates="patient")
    medical_records = relationship("MedicalRecord", back_populates="patient")
    transactions = relationship("Transaction", back_populates="user")
    history_records = relationship("History", back_populates="patient")

class Doctor(Base):
    __tablename__ = "Doctors"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("Profiles.id"), nullable=True)
    name = Column(String, nullable=False)
    specialty = Column(String, nullable=False)
    area = Column(String, nullable=False)
    bio = Column(Text, nullable=True)
    rating = Column(Float, default=4.5)
    review_count = Column(Integer, default=0)
    consultation_fee = Column(Integer, default=150)
    is_available = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Verification fields
    hpcsa_number = Column(String, nullable=True)
    id_number = Column(String, nullable=True)
    verification_status = Column(
        String, default="pending"
    )  # pending, basic, verified, rejected
    profile_completed = Column(Boolean, default=False)

    # Earnings (from completed appointments)
    total_earnings = Column(Integer, default=0)
    pending_earnings = Column(Integer, default=0)

    # Gig Economy - Custom Pricing
    quick_chat_price = Column(Integer, default=50)
    video_call_price = Column(Integer, default=150)
    full_consultation_price = Column(Integer, default=250)
    prescription_review_price = Column(Integer, default=80)
    report_analysis_price = Column(Integer, default=120)

    # Peak Pricing (multiplier, e.g., 1.5 = 50% increase)
    peak_pricing_multiplier = Column(Float, default=1.0)

    # Gig Mode
    is_online = Column(Boolean, default=True)  # Online/Offline toggle
    gig_mode_enabled = Column(Boolean, default=True)

    # Hashgraph for credits
    hashgraph_account_id = Column(String, nullable=True)

    # Image/photo
    photo_url = Column(String, nullable=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    appointments = relationship("Appointment", back_populates="doctor")
    prescriptions = relationship("Prescription", back_populates="doctor")
    medical_records = relationship("MedicalRecord", back_populates="doctor")


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("Profiles.id"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("Doctors.id"), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    appointment_type = Column(SQLEnum(AppointmentType), default=AppointmentType.VIDEO)
    status = Column(SQLEnum(AppointmentStatus), default=AppointmentStatus.SCHEDULED)
    reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    price_credits = Column(Integer, default=150)
    teleconsultation_status = Column(String, default="pending")

    # Gig Economy - Service Tier & Pricing
    service_tier = Column(SQLEnum(ServiceTier), default=ServiceTier.VIDEO_CALL)
    base_price = Column(Integer, default=150)  # Doctor's set price
    platform_fee = Column(Integer, default=30)  # 20% of base_price
    doctor_earnings = Column(Integer, default=120)  # 80% of base_price
    tip_amount = Column(Integer, default=0)  # 100% to doctor
    escrow_status = Column(SQLEnum(EscrowStatus), default=EscrowStatus.PENDING)

    # Convenience tracking
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    duration_minutes = Column(Integer, nullable=True)

    # Relationships
    patient = relationship(
        "User", back_populates="appointments", foreign_keys=[patient_id]
    )
    doctor = relationship("Doctor", back_populates="appointments")
    prescriptions = relationship("Prescription", back_populates="appointment")
    history = relationship("History", back_populates="appointment", uselist=False)


class Prescription(Base):
    __tablename__ = "prescriptions"

    id = Column(Integer, primary_key=True, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=False)
    patient_id = Column(Integer, ForeignKey("Profiles.id"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("Doctors.id"), nullable=False)
    medication = Column(String, nullable=False)
    dosage = Column(String, nullable=False)
    instructions = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    appointment = relationship("Appointment", back_populates="prescriptions")
    patient = relationship("User", back_populates="prescriptions")
    doctor = relationship("Doctor", back_populates="prescriptions")


class MedicalRecord(Base):
    __tablename__ = "medical_records"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("Profiles.id"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("Doctors.id"), nullable=False)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=True)
    summary = Column(Text, nullable=False)
    diagnosis = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    patient = relationship("User", back_populates="medical_records")
    doctor = relationship("Doctor", back_populates="medical_records")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("Profiles.id"), nullable=False)
    amount = Column(Integer, nullable=False)
    transaction_type = Column(
        String, nullable=False
    )  # credit_purchase, appointment_payment
    description = Column(String, nullable=True)
    payment_method = Column(String, nullable=True)  # payfast, manual
    payment_status = Column(String, default="pending")  # pending, completed, failed
    payfast_payment_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="transactions")


class History(Base):
    __tablename__ = "history"

    id = Column(Integer, primary_key=True, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=False)
    patient_id = Column(Integer, ForeignKey("Profiles.id"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("Doctors.id"), nullable=False)
    visit_summary = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    patient = relationship("User", back_populates="history_records")
    appointment = relationship("Appointment", back_populates="history")


# Create tables
def init_db():
    # Add history relationship to Appointment dynamically if needed, 
    # but we can also do it in the class definition if we move things around.
    # For now, let's just make sure the relationship exists.
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ========== ADDITIONAL MODELS ==========


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=False)
    sender_id = Column(Integer, ForeignKey("Profiles.id"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class DoctorSchedule(Base):
    __tablename__ = "doctor_schedules"

    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(Integer, ForeignKey("Doctors.id"), nullable=False)
    day_of_week = Column(Integer, nullable=False)  # 0=Monday, 6=Sunday
    start_time = Column(String, nullable=False)  # "09:00"
    end_time = Column(String, nullable=False)  # "17:00"
    is_active = Column(Boolean, default=True)

    doctor = relationship("Doctor", back_populates="schedules")


class TimeSlot(Base):
    __tablename__ = "time_slots"

    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(Integer, ForeignKey("Doctors.id"), nullable=False)
    date = Column(Date, nullable=False)
    start_time = Column(String, nullable=False)
    end_time = Column(String, nullable=False)
    is_booked = Column(Boolean, default=False)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=True)


# Add relationships to Doctor
Doctor.schedules = relationship("DoctorSchedule", back_populates="doctor")


class Tip(Base):
    __tablename__ = "tips"

    id = Column(Integer, primary_key=True, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=False)
    patient_id = Column(Integer, ForeignKey("Profiles.id"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("Doctors.id"), nullable=False)
    amount = Column(Integer, nullable=False)  # 100% goes to doctor
    created_at = Column(DateTime, default=datetime.utcnow)

    appointment = relationship("Appointment")
    patient = relationship("User", foreign_keys=[patient_id])
    doctor = relationship("Doctor", foreign_keys=[doctor_id])
