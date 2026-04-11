#!/usr/bin/env python3
"""
Initialize the SQLite database with sample data for DoctorLink.
"""

from datetime import datetime, timedelta
from database import SessionLocal, Base, engine, User, Doctor, UserRole, Appointment, AppointmentStatus, ServiceTier
from auth import hash_password

def init_sample_data():
    # Create tables
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # Create Patient
        patient = User(
            name="Test Patient",
            email="test3@test.com",
            password_hash=hash_password("pass"),
            role=UserRole.PATIENT,
            credits=500,
            email_verified=True,
            verification_level="basic"
        )
        db.add(patient)
        
        # Create Doctor User
        doctor_user = User(
            name="Dr. Smith",
            email="doc@docmail.com",
            password_hash=hash_password("test123"),
            role=UserRole.DOCTOR,
            credits=0,
            email_verified=True,
            verification_level="verified"
        )
        db.add(doctor_user)
        db.commit()
        db.refresh(doctor_user)
        
        # Create Doctor Profile
        doctor_profile = Doctor(
            user_id=doctor_user.id,
            name="Dr. Smith",
            specialty="General Practitioner",
            area="Johannesburg",
            bio="Experienced GP with 10 years of experience in family medicine.",
            consultation_fee=150,
            is_online=True,
            verification_status="verified",
            profile_completed=True
        )
        db.add(doctor_profile)
        db.commit()
        db.refresh(doctor_profile)
        
        # Create another doctor
        doctor_user2 = User(
            name="Dr. Zulu",
            email="zulu@docmail.com",
            password_hash=hash_password("test123"),
            role=UserRole.DOCTOR,
            credits=0,
            email_verified=True,
            verification_level="verified"
        )
        db.add(doctor_user2)
        db.commit()
        db.refresh(doctor_user2)
        
        doctor_profile2 = Doctor(
            user_id=doctor_user2.id,
            name="Dr. Zulu",
            specialty="Pediatrician",
            area="Cape Town",
            bio="Passionate about child healthcare.",
            consultation_fee=200,
            is_online=True,
            verification_status="verified",
            profile_completed=True
        )
        db.add(doctor_profile2)
        
        # Create a sample appointment
        appointment = Appointment(
            patient_id=patient.id,
            doctor_id=doctor_profile.id,
            timestamp=datetime.utcnow() + timedelta(days=1),
            status=AppointmentStatus.SCHEDULED,
            price_credits=150,
            service_tier=ServiceTier.VIDEO_CALL,
            base_price=150,
            platform_fee=30,
            doctor_earnings=120
        )
        db.add(appointment)
        
        db.commit()
        print("✅ Sample data initialized successfully in SQLite.")
        
    except Exception as e:
        print(f"❌ Error initializing sample data: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    init_sample_data()
