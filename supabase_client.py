"""
Supabase client configuration for DoctorLink.
Manages connection to Supabase for Auth, Database, and optional Storage.
"""

import os
from dotenv import load_dotenv
from config import settings

load_dotenv()

from supabase import create_client, Client

# Supabase Configuration
SUPABASE_URL = settings.SUPABASE_URL
SUPABASE_ANON_KEY = settings.SUPABASE_ANON_KEY
SUPABASE_SERVICE_KEY = settings.SUPABASE_SERVICE_KEY

# Global client instance
_supabase_client: Client | None = None


def get_supabase_client() -> Client:
    """Get or create Supabase client instance."""
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    return _supabase_client


def get_service_client() -> Client:
    """Get Supabase client with service role key (admin operations)."""
    if not SUPABASE_SERVICE_KEY:
        raise ValueError("SUPABASE_SERVICE_KEY not configured")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


# ==================== AUTH HELPERS ====================


async def sign_up(email: str, password: str, user_metadata: dict = None, redirect_url: str = None):
    """Register a new user."""
    client = get_supabase_client()

    # Default redirect for email confirmation
    # Should point back to the frontend deployment
    options = {"email_redirect_to": redirect_url or "http://localhost:8000/"}

    if user_metadata:
        options["data"] = user_metadata

    return client.auth.sign_up(email, password, options)


async def sign_in(email: str, password: str):
    """Login user."""
    client = get_supabase_client()
    return client.auth.sign_in_with_password(email, password)


async def sign_out():
    """Logout user."""
    client = get_supabase_client()
    return client.auth.sign_out()


async def get_current_user():
    """Get current logged in user."""
    client = get_supabase_client()
    return client.auth.get_user()


def get_session():
    """Get current session."""
    client = get_supabase_client()
    return client.auth.get_session()


# ==================== DATABASE HELPERS ====================


async def insert_record(table: str, data: dict):
    """Insert a record into a table."""
    client = get_supabase_client()
    return client.table(table).insert(data).execute()


async def select_records(
    table: str, filters: dict = None, order_by: str = None, limit: int = None
):
    """Select records from a table."""
    client = get_supabase_client()
    query = client.table(table).select("*")

    if filters:
        for key, value in filters.items():
            query = query.eq(key, value)

    if order_by:
        query = query.order(order_by, desc=True)

    if limit:
        query = query.limit(limit)

    return query.execute()


async def update_record(table: str, filters: dict, data: dict):
    """Update a record."""
    client = get_supabase_client()

    query = client.table(table).update(data)
    for key, value in filters.items():
        query = query.eq(key, value)

    return query.execute()


async def delete_record(table: str, filters: dict):
    """Delete a record."""
    client = get_supabase_client()

    query = client.table(table).delete()
    for key, value in filters.items():
        query = query.eq(key, value)

    return query.execute()


# ==================== DOCTOR HELPERS ====================


async def get_doctor_by_user_id(user_id: str):
    """Get doctor profile by user ID."""
    result = await select_records("doctors", {"user_id": user_id})
    return result.data[0] if result.data else None


async def get_online_doctors():
    """Get all online doctors."""
    result = await select_records("doctors", {"is_online": True})
    return result.data


async def create_doctor(
    user_id: str, name: str, specialty: str = "General Practitioner"
):
    """Create doctor profile."""
    return await insert_record(
        "doctors",
        {
            "user_id": user_id,
            "name": name,
            "specialty": specialty,
            "area": "",
            "rating": 0,
            "review_count": 0,
            "is_available": True,
            "is_online": True,
            "quick_chat_price": 50,
            "video_call_price": 150,
            "full_consultation_price": 250,
            "prescription_review_price": 80,
            "report_analysis_price": 120,
            "peak_pricing_multiplier": 1.0,
            "gig_mode_enabled": True,
        },
    )


# ==================== APPOINTMENT HELPERS ====================


async def create_appointment(
    patient_id: str,
    doctor_id: int,
    timestamp: str,
    service_tier: str,
    reason: str = None,
):
    """Create a new appointment."""
    return await insert_record(
        "appointments",
        {
            "patient_id": patient_id,
            "doctor_id": doctor_id,
            "timestamp": timestamp,
            "appointment_type": "VIDEO",
            "status": "SCHEDULED",
            "service_tier": service_tier,
            "reason": reason,
            "escrow_status": "PENDING",
        },
    )


async def get_patient_appointments(patient_id: str):
    """Get all appointments for a patient."""
    result = await select_records(
        "appointments", {"patient_id": patient_id}, order_by="timestamp"
    )
    return result.data


async def get_doctor_appointments(doctor_id: int):
    """Get all appointments for a doctor."""
    result = await select_records(
        "appointments", {"doctor_id": doctor_id}, order_by="timestamp"
    )
    return result.data


# ==================== PROFILE HELPERS ====================


async def get_profile(user_id: str):
    """Get user profile."""
    result = await select_records("profiles", {"id": user_id})
    return result.data[0] if result.data else None


async def create_profile(user_id: str, email: str, name: str, role: str = "PATIENT"):
    """Create user profile."""
    return await insert_record(
        "profiles",
        {
            "id": user_id,
            "email": email,
            "name": name,
            "role": role,
            "credits": 500 if role == "PATIENT" else 0,
        },
    )


async def update_profile_credits(user_id: str, credits: int):
    """Update user credits."""
    return await update_record("profiles", {"id": user_id}, {"credits": credits})
