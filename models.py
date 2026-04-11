#!/usr/bin/env python3
"""
ORM model definitions for DoctorLink.

Includes User, Doctor, Appointment, Review, TeleconsultationRoom models
with appropriate relationships and constraints.
"""

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Text,
    Enum as SQLEnum,
)
from sqlalchemy.orm import relationship

from .database import Base

# ----------------------------------------------------------------------
# Enums
# ----------------------------------------------------------------------
class RoomStatus(PyEnum):
    WAITING = "WAITING"
    LIVE = "LIVE"
    ENDED = "ENDED"


class AppointmentStatus(PyEnum):
    SCHEDULED = "SCHEDULED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class UserRole(PyEnum):
    PATIENT = "PATIENT"
    DOCTOR = "DOCTOR"
    ADMIN = "ADMIN"


# ----------------------------------------------------------------------
# User model – represents a system user (patient or doctor)
# ----------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=True) # Added for secure auth
    role = Column(SQLEnum(UserRole), nullable=False, default=UserRole.PATIENT)
    credits = Column(Integer, default=0, nullable=False)
    
    # 🔒 Security: Encrypted Field representation
    # In production, use sqlalchemy-utils EncryptedType or db-level TDE
    national_id_encrypted = Column(String, nullable=True) 

    # 🗑️ Compliance: Soft Deletes
    is_deleted = Column(Integer, default=0, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    # Relationships
    appointments_as_patient = relationship(
        "Appointment",
        back_populates="patient",
        foreign_keys="Appointment.patient_id",
        cascade="all, delete-orphan",
    )
    appointments_as_doctor = relationship(
        "Appointment",
        back_populates="doctor_user",
        foreign_keys="Appointment.doctor_user_id",
        cascade="all, delete-orphan",
    )
    reviews_written = relationship(
        "Review",
        back_populates="user",
        foreign_keys="Review.user_id",
        cascade="all, delete-orphan",
    )
    teleconsultation_rooms = relationship(
        "TeleconsultationRoom",
        back_populates="patient",
        cascade="all, delete-orphan",
    )
    history_records = relationship(
        "History",
        back_populates="patient",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} name={self.name} email={self.email}>"


# ----------------------------------------------------------------------
# Doctor model – specific details for medical professionals
# ----------------------------------------------------------------------
class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True) # Link to User
    name = Column(String, nullable=False)
    area = Column(String, nullable=True)          # Geographic area
    specialty = Column(String, nullable=True)    # Medical specialty

    # Relationships
    user = relationship("User")
    appointments = relationship(
        "Appointment",
        back_populates="doctor",
        cascade="all, delete-orphan",
    )
    reviews_received = relationship(
        "Review",
        back_populates="doctor_ref", # Renamed to avoid confusion if needed
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Doctor id={self.id} name={self.name}>"


# ----------------------------------------------------------------------
# Appointment model
# ----------------------------------------------------------------------
class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    doctor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True) # Linked doctor user
    timestamp = Column(DateTime, nullable=False)
    price_credits = Column(Integer, nullable=False, default=0)
    status = Column(SQLEnum(AppointmentStatus), nullable=False, default=AppointmentStatus.SCHEDULED)
    teleconsultation_status = Column(SQLEnum(RoomStatus), nullable=False, default=RoomStatus.WAITING)

    patient = relationship("User", back_populates="appointments_as_patient", foreign_keys=[patient_id])
    doctor_user = relationship("User", back_populates="appointments_as_doctor", foreign_keys=[doctor_user_id])
    doctor = relationship("Doctor", back_populates="appointments")
    history = relationship("History", back_populates="appointment", uselist=False)

    def __repr__(self) -> str:
        return f"<Appointment id={self.id} patient_id={self.patient_id} doctor_id={self.doctor_id}>"


# ----------------------------------------------------------------------
# History model – medical records/visit summaries
# ----------------------------------------------------------------------
class History(Base):
    __tablename__ = "history"

    id = Column(Integer, primary_key=True, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=False)
    patient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    visit_summary = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    appointment = relationship("Appointment", back_populates="history")
    patient = relationship("User", back_populates="history_records")

    def __repr__(self) -> str:
        return f"<History id={self.id} appointment_id={self.appointment_id}>"


# ----------------------------------------------------------------------
# Review model
# ----------------------------------------------------------------------
class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)   # author
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    rating = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="reviews_written")
    doctor_ref = relationship("Doctor", back_populates="reviews_received")

    def __repr__(self) -> str:
        return f"<Review id={self.id} rating={self.rating}>"


# ----------------------------------------------------------------------
# TeleconsultationRoom model
# ----------------------------------------------------------------------
class TeleconsultationRoom(Base):
    __tablename__ = "teleconsultation_rooms"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(SQLEnum(RoomStatus), nullable=False, default=RoomStatus.WAITING)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    patient = relationship("User", back_populates="teleconsultation_rooms")

    def __repr__(self) -> str:
        return f"<TeleconsultationRoom id={self.id} status={self.status}>"


# ----------------------------------------------------------------------
# Transaction model – audit log for credit changes
# ----------------------------------------------------------------------
class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Integer, nullable=False) # Positive for addition, negative for deduction
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")

    def __repr__(self) -> str:
        return f"<Transaction id={self.id} user_id={self.user_id} amount={self.amount}>"