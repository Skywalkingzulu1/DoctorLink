import os
import sys
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta, timezone
from jose import jwt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import app
from database import FilebaseSession, User, Doctor, AppointmentStatus, UserRole, Appointment
from filebase_db import _cache
from config import settings

client = TestClient(app)

def _clear_all_tables():
    """Clear all in-memory caches so tests start fresh."""
    _cache.clear()
    # We don't delete Filebase remote — each test run starts fresh locally

def setup_db():
    db = FilebaseSession()

    patient = User(name="Test Patient", email="test@patient.com", credits=500, role=UserRole.PATIENT, password_hash="hash")
    doctor_user = User(name="Test Doctor", email="test@doctor.com", credits=0, role=UserRole.DOCTOR, password_hash="hash")

    db.add(patient)
    db.add(doctor_user)
    db.commit()
    
    # Refresh to get IDs
    patient = db.query(User).filter(User.email == "test@patient.com").first()
    doctor_user = db.query(User).filter(User.email == "test@doctor.com").first()
    db.close()

    # Create doctor profile
    db2 = FilebaseSession()
    doctor = Doctor(name="Dr. Test", specialty="General", area="Test Area", user_id=doctor_user.id,
                    consultation_fee=150, is_available=True, is_online=True, gig_mode_enabled=True,
                    profile_completed=True, verification_status="verified")
    db2.add(doctor)
    db2.commit()
    # Refresh to get ID
    doctor = db2.query(Doctor).filter(Doctor.user_id == doctor_user.id).first()
    db2.close()

    return patient, doctor_user, doctor


def make_token(email: str):
    payload = {"sub": email, "exp": datetime.now(timezone.utc) + timedelta(hours=1)}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


@pytest.fixture(autouse=True)
def reset():
    _clear_all_tables()


def test_root():
    response = client.get("/")
    assert response.status_code == 200


def test_login():
    # First register
    resp = client.post("/api/auth/register", json={
        "email": "login@test.com", "password": "test123",
        "name": "Login Tester", "role": "PATIENT"
    })
    assert resp.status_code == 200, resp.text

    # Then login
    resp = client.post("/api/auth/token", data={
        "username": "login@test.com", "password": "test123"
    }, headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "access_token" in data
    return data["access_token"]


def test_appointment_flow():
    patient, doctor_user, doctor = setup_db()
    token = make_token(patient.email)

    # Get doctors
    resp = client.get("/api/doctors", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    doctors = resp.json()
    assert len(doctors) > 0

    # Book appointment
    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
    resp = client.post("/api/appointments", json={
        "doctor_id": doctor.id,
        "timestamp": tomorrow.isoformat(),
        "appointment_type": "VIDEO",
        "reason": "Test appointment"
    }, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    apt = resp.json()
    assert "id" in apt

    # Get appointments
    resp = client.get("/api/appointments", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    appts = resp.json()
    assert len(appts) > 0


def test_profile():
    patient, _, _ = setup_db()
    token = make_token(patient.email)

    resp = client.get("/api/profile", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == patient.email


def test_doctor_profile():
    patient, doctor_user, doctor = setup_db()

    # Doctor token
    token = make_token(doctor_user.email)

    resp = client.get("/api/profile/doctor", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Dr. Test"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
