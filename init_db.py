#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./doctorlink.db"

    class Config:
        extra = "ignore"


settings = Settings()

DATABASE_URL = settings.DATABASE_URL
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
    if DATABASE_URL.startswith("sqlite")
    else {},
    echo=False,
)

Base = declarative_base()

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Text,
    Enum as SQLEnum,
)
from enum import Enum as PyEnum


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


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=True)
    role = Column(SQLEnum(UserRole), nullable=False, default=UserRole.PATIENT)
    credits = Column(Integer, default=0, nullable=False)
    national_id_encrypted = Column(String, nullable=True)
    is_deleted = Column(Integer, default=0, nullable=False)
    deleted_at = Column(DateTime, nullable=True)


class Doctor(Base):
    __tablename__ = "doctors"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    name = Column(String, nullable=False)
    area = Column(String, nullable=True)
    specialty = Column(String, nullable=True)


class Appointment(Base):
    __tablename__ = "appointments"
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    doctor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    timestamp = Column(DateTime, nullable=False)
    price_credits = Column(Integer, nullable=False, default=0)
    status = Column(
        SQLEnum(AppointmentStatus), nullable=False, default=AppointmentStatus.SCHEDULED
    )
    teleconsultation_status = Column(
        SQLEnum(RoomStatus), nullable=False, default=RoomStatus.WAITING
    )


class History(Base):
    __tablename__ = "history"
    id = Column(Integer, primary_key=True, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=False)
    patient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    visit_summary = Column(Text, nullable=False)
    created_at = Column(DateTime, default=__import__("datetime").datetime.utcnow)


class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Integer, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=__import__("datetime").datetime.utcnow)


Base.metadata.create_all(bind=engine)
print("[OK] Database tables created")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

existing = db.query(Doctor).first()
if not existing:
    johannesburg_doctors = [
        {
            "name": "Dr. Sarah Mitchell",
            "area": "Sandton",
            "specialty": "General Practitioner",
        },
        {
            "name": "Dr. James van der Merwe",
            "area": "Johannesburg CBD",
            "specialty": "Cardiology",
        },
        {"name": "Dr. Priya Naidoo", "area": "Rosebank", "specialty": "Dermatology"},
        {"name": "Dr. Michael Brown", "area": "Fourways", "specialty": "Pediatrics"},
        {"name": "Dr. Anneke Smith", "area": "Melville", "specialty": "Psychiatry"},
        {
            "name": "Dr. Thabo Molefe",
            "area": "Alexandra",
            "specialty": "General Practitioner",
        },
        {
            "name": "Dr. Fatima Hassan",
            "area": "Midrand",
            "specialty": "Obstetrics & Gynecology",
        },
        {"name": "Dr. Robert Jones", "area": "Randburg", "specialty": "Orthopedics"},
        {
            "name": "Dr. Lindiwe Dlamini",
            "area": "Soweto",
            "specialty": "General Practitioner",
        },
        {"name": "Dr. Craig Petersen", "area": "Parktown", "specialty": "Neurology"},
        {
            "name": "Dr. Maria van Wyk",
            "area": "Lyndhurst",
            "specialty": "Family Medicine",
        },
        {
            "name": "Dr. Bongani Khoza",
            "area": "Daveyton",
            "specialty": "Internal Medicine",
        },
    ]
    for doc_data in johannesburg_doctors:
        doctor = Doctor(**doc_data)
        db.add(doctor)
    db.commit()
    print("[OK] Seeded 12 Johannesburg doctors")
else:
    print("Doctors already exist - skipping seed")

db.close()
