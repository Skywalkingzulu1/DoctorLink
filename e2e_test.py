import os
import sys
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
from jose import jwt

# If you need the current directory in path, use:
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import app
from database import SessionLocal, Base, engine, User, Doctor, AppointmentStatus, UserRole
from config import settings

client = TestClient(app)

def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    # Use UserRole enum if available, or just string if it's a string column
    # database.py uses SQLEnum(UserRole)
    patient = User(name="Test Patient", email="test@patient.com", credits=500, role=UserRole.PATIENT, password_hash="hash")
    doctor_user = User(name="Test Doctor", email="test@doctor.com", credits=0, role=UserRole.DOCTOR, password_hash="hash")
    db.add(patient)
    db.add(doctor_user)
    db.commit()
    db.refresh(patient)
    db.refresh(doctor_user)
    
    doc = Doctor(user_id=doctor_user.id, name="Dr. Test", specialty="Testing", area="Test Area", is_online=True)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    
    # Return patient token, doctor token, doctor id
    p_token = jwt.encode({"sub": str(patient.id), "user_id": patient.id, "exp": datetime.utcnow() + timedelta(days=1)}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    d_token = jwt.encode({"sub": str(doctor_user.id), "user_id": doctor_user.id, "exp": datetime.utcnow() + timedelta(days=1)}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return p_token, d_token, doc.id, patient.id, doctor_user.id

def test_full_flow():
    print("Testing End-to-End DoctorLink Flow...")
    p_token, d_token, doc_id, p_id, d_id = setup_db()
    p_headers = {"Authorization": f"Bearer {p_token}"}
    d_headers = {"Authorization": f"Bearer {d_token}"}
    
    # 1. Check me
    res = client.get("/api/auth/me", headers=p_headers)
    assert res.status_code == 200, f"Failed GET /api/auth/me: {res.text}"
    assert res.json()["credits"] == 500
    print("✅ Get /me successful")
    
    # 2. Book appointment (should deduct credits immediately)
    future_time = (datetime.utcnow() + timedelta(days=1)).isoformat()
    res = client.post("/api/appointments", json={
        "doctor_id": doc_id,
        "timestamp": future_time,
        "service_tier": "VIDEO_CALL",
        "appointment_type": "VIDEO"
    }, headers=p_headers)
    assert res.status_code == 201, f"Failed POST /api/appointments: {res.text}"
    appt_id = res.json()["id"]
    print("✅ Appointment booked successfully")
    
    # 2b. Verify credit deduction
    res = client.get("/api/auth/me", headers=p_headers)
    assert res.json()["credits"] == 350, f"Credits not deducted! Got {res.json()['credits']}"
    print("✅ Credits automatically deducted upon booking.")
    
    # 3. Update status to ACTIVE (Doctor does this)
    res = client.patch(f"/api/appointments/{appt_id}", json={"status": "ACTIVE"}, headers=d_headers)
    assert res.status_code == 200, f"Failed PATCH /api/appointments: {res.text}"
    print("✅ Appointment status updated to ACTIVE by doctor")
    
    # 4. Telehealth signal exchange
    res = client.post(f"/api/telehealth/rooms/{appt_id}/signals", json={
        "target_id": d_id,
        "signal_data": "offer"
    }, headers=p_headers)
    assert res.status_code == 200, f"Failed POST signals: {res.text}"
    print("✅ WebRTC Signal Exchange endpoint successful")
    
    # 5. Upload Meeting Summary
    res = client.post(f"/api/telehealth/summary", json={
        "appointment_id": appt_id,
        "summary": "Patient is doing great. No issues."
    }, headers=d_headers)
    assert res.status_code == 201, f"Failed POST summary: {res.text}"
    print("✅ Meeting summary uploaded successfully")

    # 6. Verify status is COMPLETED
    res = client.get(f"/api/appointments/{appt_id}", headers=p_headers)
    assert res.json()["status"] == "COMPLETED"
    print("✅ Appointment status is COMPLETED")

    print("🚀 All E2E Tests Passed!")

def f(s):
    return s.format() # Just a helper for f-strings if I forgot some

if __name__ == "__main__":
    test_full_flow()
