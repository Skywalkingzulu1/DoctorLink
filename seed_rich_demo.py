"""
Seed script for DoctorLink - Rich Triage & Home Visit Demo.
Creates a patient with a detailed home visit appointment.
"""
import os
import sys
from datetime import datetime, timedelta
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio

from database import SessionLocal, User, Doctor, Appointment, AppointmentType, ServiceTier, AppointmentStatus
from auth import hash_password
from api.somnia_agent import run_all_triage_tools

async def seed_rich_demo():
    db = SessionLocal()
    try:
        # 1. Create Demo Patient
        patient_email = "patient_demo@test.com"
        patient = db.query(User).filter(User.email == patient_email).first()
        if not patient:
            patient = User(
                name="John Doe (Demo Patient)",
                email=patient_email,
                password_hash=hash_password("pass"),
                role="PATIENT",
                credits=1000,
                email_verified=True
            )
            db.add(patient)
            db.commit()
            print(f"Created patient: {patient_email}")

        # 2. Get Demo Doctor
        doc_email = "doc_sarah@test.com"
        doctor = db.query(Doctor).join(User).filter(User.email == doc_email).first()
        if not doctor:
            doc_user = User(
                name="Dr. Sarah Smith",
                email=doc_email,
                password_hash=hash_password("test123"),
                role="DOCTOR",
                credits=0
            )
            db.add(doc_user)
            db.commit()
            doctor = db.query(Doctor).filter(Doctor.user_id == doc_user.id).first()
            if not doctor:
                doctor = Doctor(
                    user_id=doc_user.id,
                    name=doc_user.name,
                    specialty="General Practitioner",
                    area="Johannesburg",
                    is_online=True,
                    video_call_price=150
                )
                db.add(doctor)
                db.commit()
            print(f"Created doctor: {doc_email}")

        # 3. Create Rich Triage Data
        triage_data = {
            "chief_complaint": "Severe abdominal pain and nausea",
            "duration": "24 hours",
            "pain_scale": "8",
            "medications": "Aspirin, Vitamin C",
            "allergies": "Penicillin, Peanuts",
            "pre_existing_conditions": "Mild Gastritis",
            "red_flags": "Localized sharp pain in lower right quadrant",
            "timestamp": datetime.utcnow().isoformat()
        }
        triage_json = json.dumps(triage_data)

        # 4. Generate Grounded AI Medical Analysis (using new EM script system)
        print("Generating grounded AI clinical analysis...")
        ai_results = await run_all_triage_tools(triage_json)

        # 5. Create Home Visit Appointment
        # Delete existing demo appointments for this patient to refresh
        db.query(Appointment).filter(Appointment.patient_id == patient.id).delete()
        db.commit()

        appt = Appointment(
            patient_id=patient.id,
            doctor_id=doctor.id,
            timestamp=datetime.utcnow() + timedelta(hours=2),
            appointment_type=AppointmentType.INPERSON,
            service_tier=ServiceTier.FULL_CONSULTATION,
            reason="Abdominal Pain - Home Visit",
            location="123 Health Street, Sandton, Johannesburg",
            status=AppointmentStatus.SCHEDULED,
            price_credits=250,
            triage_data=triage_json,
            triage_tools_results=json.dumps(ai_results)
        )
        db.add(appt)
        db.commit()
        print(f"Created rich triage home visit appointment for {patient.name} with EM Script System results.")

    except Exception as e:
        print(f"Error seeding: {e}")
        import traceback
        print(traceback.format_exc())
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(seed_rich_demo())
