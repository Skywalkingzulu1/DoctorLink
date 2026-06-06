#!/usr/bin/env python3
"""
Initialize the SQLite database with sample data for Doctors on Wheels.
"""

from datetime import datetime, timedelta
from database import SessionLocal, Base, engine, User, Doctor, UserRole, Appointment, AppointmentStatus, ServiceTier
from auth import hash_password

def init_sample_data():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        patient = User(
            name="Test Patient",
            email="test3@test.com",
            password_hash=hash_password("pass"),
            role=UserRole.PATIENT,
            credits=350,
            t800_balance=2000,
            is_active=True,
            email_verified=True,
            verification_level="basic",
            somnia_address="0x9E2b44069c8D7Fb780A7b093Dd21153BF10E8B9A",
        )
        db.add(patient)
        db.commit()
        db.refresh(patient)

        sam_user = User(
            name="Dr. Sam Luzulane",
            email="sam@docmail.com",
            password_hash=hash_password("test123"),
            role=UserRole.DOCTOR,
            credits=0,
            t800_balance=2400,
            is_active=True,
            email_verified=True,
            verification_level="verified",
            somnia_address="0x189a400A44b477bc453E67f20e4e2dd9b2715b49",
        )
        db.add(sam_user)
        db.commit()
        db.refresh(sam_user)

        sam_doctor = Doctor(
            user_id=sam_user.id,
            name="Dr. Sam Luzulane",
            specialty="Emergency Medicine",
            area="Gauteng",
            bio="Emergency medicine specialist with 15 years experience.",
            rating=5.0,
            review_count=0,
            consultation_fee=800,
            is_available=True,
            verification_status="verified",
            profile_completed=True,
            is_online=True,
            gig_mode_enabled=True,
            quick_chat_price=400,
            video_call_price=800,
            full_consultation_price=1500,
            prescription_review_price=300,
            report_analysis_price=500,
            peak_pricing_multiplier=1.0,
            total_earnings=0,
            pending_earnings=0,
            hpcsa_number="MP 0123456",
            id_number="8501015000081",
        )
        db.add(sam_doctor)

        ai_user = User(
            name="AI Doctor",
            email="ai@somnia.network",
            password_hash=hash_password("agent123"),
            role=UserRole.DOCTOR,
            credits=0,
            t800_balance=0,
            is_active=True,
            email_verified=True,
            verification_level="verified",
            somnia_address="0x0000000000000000000000000000000000000000",
        )
        db.add(ai_user)
        db.commit()
        db.refresh(ai_user)

        ai_doctor = Doctor(
            user_id=ai_user.id,
            name="AI Doctor",
            specialty="General Practice (AI)",
            area="Global",
            bio="Autonomous AI medical assistant powered by Somnia LLM.",
            rating=5.0,
            review_count=0,
            consultation_fee=50,
            is_available=True,
            verification_status="verified",
            profile_completed=True,
            is_online=True,
            gig_mode_enabled=True,
            quick_chat_price=50,
            video_call_price=50,
            full_consultation_price=50,
            prescription_review_price=50,
            report_analysis_price=50,
            peak_pricing_multiplier=1.0,
            total_earnings=0,
            pending_earnings=0,
        )
        db.add(ai_doctor)
        db.commit()
        
        appointment = Appointment(
            patient_id=patient.id,
            doctor_id=sam_doctor.id,
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
