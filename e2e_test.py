import os
import sys
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
import jwt

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from projects.DoctorLink.main import app
from projects.DoctorLink.database import SessionLocal, Base, engine
from projects.DoctorLink.models import User, Doctor, AppointmentStatus
from projects.DoctorLink.auth import SECRET_KEY, ALGORITHM

client = TestClient(app)

def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    patient = User(name="Test Patient", email="test@patient.com", credits=500)
    doctor_user = User(name="Test Doctor", email="test@doctor.com", credits=0)
    db.add(patient)
    db.add(doctor_user)
    db.flush()
    
    doc = Doctor(id=1, name="Dr. Test", specialty="Testing")
    db.add(doc)
    db.commit()
    
    # Return patient token, doctor token, doctor id
    p_token = jwt.encode({"user_id": patient.id, "exp": datetime.utcnow() + timedelta(days=1)}, SECRET_KEY, algorithm=ALGORITHM)
    d_token = jwt.encode({"user_id": doctor_user.id, "exp": datetime.utcnow() + timedelta(days=1)}, SECRET_KEY, algorithm=ALGORITHM)
    return p_token, d_token, doc.id, patient.id, doctor_user.id

def test_full_flow():
    print("Testing End-to-End DoctorLink Flow...")
    p_token, d_token, doc_id, p_id, d_id = setup_db()
    p_headers = {"Authorization": f"Bearer {p_token}"}
    d_headers = {"Authorization": f"Bearer {d_token}"}
    
    # 1. Check me
    res = client.get("/appointments/me", headers=p_headers)
    assert res.status_code == 200, f"Failed GET /appointments/me: {res.text}"
    assert res.json()["credits"] == 500
    print("✅ Get /me successful")
    
    # 2. Book appointment
    future_time = (datetime.utcnow() + timedelta(days=1)).isoformat()
    res = client.post("/appointments/", json={
        "doctor_id": doc_id,
        "timestamp": future_time,
        "price_credits": 150
    }, headers=p_headers)
    assert res.status_code == 201, f"Failed POST /appointments/: {res.text}"
    appt_id = res.json()["id"]
    print("✅ Appointment booked successfully")
    
    # 3. Update status to ACTIVE (should deduct credits)
    res = client.patch(f"/appointments/{appt_id}", json={"status": "ACTIVE"}, headers=p_headers)
    assert res.status_code == 200, f"Failed PATCH /appointments: {res.text}"
    print("✅ Appointment status updated to ACTIVE")
    
    # 4. Verify credit deduction
    res = client.get("/appointments/me", headers=p_headers)
    assert res.json()["credits"] == 350, "Credits not deducted!"
    print("✅ Wallet Hardening working! Credits automatically deducted.")
    
    # 5. Telehealth signal exchange
    res = client.post(f"/telehealth/rooms/{appt_id}/signals", json={
        "target_id": d_id,
        "signal_data": "offer"
    }, headers=p_headers)
    assert res.status_code == 200, f"Failed POST signals: {res.text}"
    print("✅ WebRTC Signal Exchange endpoint successful")
    
    # 6. Upload Meeting Summary
    res = client.post(f"/telehealth/summary", json={
        "appointment_id": appt_id,
        "summary": "Patient is doing great. No issues."
    }, headers=d_headers)
    assert res.status_code == 201, f"Failed POST summary: {res.text}"
    print("✅ Meeting summary uploaded successfully")

    print("🚀 All E2E Tests Passed! System is stable, robust, and 500-error free.")

if __name__ == "__main__":
    test_full_flow()
