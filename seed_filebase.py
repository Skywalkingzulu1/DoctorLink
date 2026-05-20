"""
Seed Filebase with demo data if the bucket is empty.
Run on first deploy or when resetting demo data.
"""

import json
from filebase_db import _client, BUCKET, _cache
from config import settings

DEMO_USERS = [
    {"id": 1, "email": "test3@test.com", "password_hash": "$2b$12$kJag16IE8NskFyUL56muheP40MnBz96OngvTnBBN4wGLVutzwK35G", "name": "Test Patient", "role": "PATIENT", "credits": 350, "t800_balance": 2000, "is_active": True, "email_verified": True, "phone_verified": False, "verification_level": "basic", "somnia_address": "0x9E2b44069c8D7Fb780A7b093Dd21153BF10E8B9A", "is_deleted": False, "phone": None, "hashgraph_account_id": None, "somnia_private_key": None, "inconvenience_discount_amount": 0, "inconvenience_discount_active": False, "inconvenience_discount_reason": None, "created_at": "2026-05-18T19:46:22"},
    {"id": 2, "email": "doc@docmail.com", "password_hash": "$2b$12$.0S9hUbN.eFCKCejdSBZz.bpGnitAUWV88qvJKOLJ6jW/sZx.xW..", "name": "Dr. Alice", "role": "DOCTOR", "credits": 0, "t800_balance": 2400, "is_active": True, "email_verified": True, "phone_verified": False, "verification_level": "verified", "somnia_address": "0x189a400A44b477bc453E67f20e4e2dd9b2715b49", "is_deleted": False, "phone": None, "hashgraph_account_id": None, "somnia_private_key": None, "inconvenience_discount_amount": 0, "inconvenience_discount_active": False, "inconvenience_discount_reason": None, "created_at": "2026-05-18T19:46:22"},
    {"id": 3, "email": "platform@doctorlink.co.za", "password_hash": "", "name": "Platform Account", "role": "PATIENT", "credits": 0, "t800_balance": 600, "is_active": True, "email_verified": False, "phone_verified": False, "verification_level": "none", "is_deleted": False, "phone": None, "hashgraph_account_id": None, "somnia_address": None, "somnia_private_key": None, "inconvenience_discount_amount": 0, "inconvenience_discount_active": False, "inconvenience_discount_reason": None, "created_at": "2026-05-18T19:46:22"},
]

DEMO_DOCTORS = [
    {"id": 1, "user_id": 2, "name": "Dr. Smith", "specialty": "General Practitioner", "area": "Johannesburg", "bio": "Experienced GP with 10 years of experience in family medicine.", "rating": 4.5, "review_count": 0, "consultation_fee": 150, "is_available": True, "verification_status": "verified", "profile_completed": True, "is_online": True, "gig_mode_enabled": True, "quick_chat_price": 50, "video_call_price": 150, "full_consultation_price": 250, "prescription_review_price": 80, "report_analysis_price": 120, "peak_pricing_multiplier": 1.0, "total_earnings": 0, "pending_earnings": 0, "subscription_active": False, "photo_url": None, "hpcsa_number": None, "id_number": None, "hashgraph_account_id": None, "subscription_end": None, "subscription_stt_paid": 0.0, "created_at": "2026-05-18T19:46:22"},
    {"id": 2, "user_id": 3, "name": "Dr. Zulu", "specialty": "Pediatrician", "area": "Cape Town", "bio": "Passionate about child healthcare.", "rating": 4.5, "review_count": 0, "consultation_fee": 200, "is_available": True, "verification_status": "verified", "profile_completed": True, "is_online": True, "gig_mode_enabled": True, "quick_chat_price": 50, "video_call_price": 150, "full_consultation_price": 250, "prescription_review_price": 80, "report_analysis_price": 120, "peak_pricing_multiplier": 1.0, "total_earnings": 0, "pending_earnings": 0, "subscription_active": False, "photo_url": None, "hpcsa_number": None, "id_number": None, "hashgraph_account_id": None, "subscription_end": None, "subscription_stt_paid": 0.0, "created_at": "2026-05-18T19:46:22"},
]

DEMO_APPOINTMENTS = [
    {"id": 1, "patient_id": 1, "doctor_id": 1, "status": "SCHEDULED", "escrow_status": "PENDING", "appointment_type": "VIDEO", "service_tier": "VIDEO_CALL", "base_price": 150, "platform_fee": 30, "doctor_earnings": 120, "price_credits": 150, "tip_amount": 0, "reason": "Annual checkup", "notes": None, "teleconsultation_status": "pending", "platform_fee_t800": 0, "somnia_tx_hash": None, "somnia_release_tx": None, "somnia_refund_tx": None, "somnia_agent_results": None, "started_at": None, "ended_at": None, "duration_minutes": None, "timestamp": "2026-05-25T10:00:00", "created_at": "2026-05-18T19:46:22"},
    {"id": 2, "patient_id": 1, "doctor_id": 1, "status": "SCHEDULED", "escrow_status": "PENDING", "appointment_type": "VIDEO", "service_tier": "FULL_CONSULTATION", "base_price": 250, "platform_fee": 50, "doctor_earnings": 200, "price_credits": 250, "tip_amount": 0, "reason": "Follow-up consultation", "notes": None, "teleconsultation_status": "pending", "platform_fee_t800": 0, "somnia_tx_hash": None, "somnia_release_tx": None, "somnia_refund_tx": None, "somnia_agent_results": None, "started_at": None, "ended_at": None, "duration_minutes": None, "timestamp": "2026-05-26T14:00:00", "created_at": "2026-05-18T19:46:22"},
]


def seed():
    client = _client()
    has_data = False
    try:
        objs = client.list_objects_v2(Bucket=BUCKET, Prefix="db/", MaxKeys=1)
        if objs.get("KeyCount", 0) > 0:
            has_data = True
    except:
        pass

    if has_data:
        print("Filebase already has data, skipping seed.")
        return

    tables = {
        "Profiles": DEMO_USERS,
        "Doctors": DEMO_DOCTORS,
        "appointments": DEMO_APPOINTMENTS,
    }

    for table_name, rows in tables.items():
        key = f"db/{table_name}.json"
        body = json.dumps(rows, indent=2).encode("utf-8")
        client.put_object(Bucket=BUCKET, Key=key, Body=body)
        print(f"Seeded {table_name}: {len(rows)} rows")

    print("Seed complete!")


if __name__ == "__main__":
    seed()
