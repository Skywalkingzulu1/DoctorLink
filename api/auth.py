"""
Auth API endpoints for Doctors on Wheels.
Integrated with Somnia Agentic L1 for automatic wallet creation.
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, ConfigDict
import boto3
from botocore.config import Config

from database import get_db, User, UserRole, Doctor, Patient
from auth import hash_password, verify_password, create_access_token, get_current_user
from config import settings
from api.storage import get_public_url, object_exists
from somnia.wallet import create_wallet_for_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


def get_avatar_url(user_id: int, role: str = "PATIENT") -> str | None:
    """Get avatar URL from Filebase bucket if exists."""
    key = f"avatars/{user_id}.jpg"
    try:
        if object_exists(key):
            return get_public_url(key)
        return None
    except:
        return None


# Pydantic models
class UserResponse(BaseModel):
    id: int
    email: str
    name: str
    role: str
    phone: str | None
    credits: int
    email_verified: bool = False
    phone_verified: bool = False
    verification_level: str = "none"
    avatar_url: str | None = None
    somnia_address: str | None = None

    model_config = ConfigDict(from_attributes=True)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: str = "PATIENT"
    phone: str | None = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_200_OK
)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user."""
    # Check if email exists
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        # Return existing user (idempotent register)
        avatar_url = get_avatar_url(existing_user.id, existing_user.role)
        return UserResponse(
            id=existing_user.id,
            email=existing_user.email,
            name=existing_user.name,
            role=existing_user.role.value if hasattr(existing_user.role, "value") else str(existing_user.role),
            phone=existing_user.phone,
            credits=existing_user.credits,
            email_verified=existing_user.email_verified,
            phone_verified=existing_user.phone_verified,
            verification_level=existing_user.verification_level or "none",
            avatar_url=avatar_url,
            somnia_address=existing_user.somnia_address,
        )

    # Validate role
    try:
        role = UserRole(request.role.upper())
    except ValueError:
        role = UserRole.PATIENT

    # Create user
    user = User(
        email=request.email,
        password_hash=hash_password(request.password),
        name=request.name,
        role=role,
        phone=request.phone,
        credits=500 if role == UserRole.PATIENT else 0,
        is_active=True,
        is_deleted=False,
        email_verified=True,  # Auto-verify for now
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Create Somnia wallet for new user
    somnia_wallet = None
    try:
        somnia_wallet = create_wallet_for_user(user.id)
    except Exception as e:
        import traceback
        print(f"Somnia wallet creation failed: {e}")
        print(traceback.format_exc())

    # Auto-create doctor profile if registering as DOCTOR
    if role == UserRole.DOCTOR:
        doctor = Doctor(
            user_id=user.id,
            name=user.name,
            specialty="General Practitioner",  # Default, can be updated
            area="",
            is_available=True,
            verification_status="basic",  # Basic verification on signup
            profile_completed=False,
            quick_chat_price=50,
            video_call_price=150,
            full_consultation_price=250,
            prescription_review_price=80,
            report_analysis_price=120,
            peak_pricing_multiplier=1.0,
            is_online=True,  # Default to online (gig mode)
            gig_mode_enabled=True,
        )
        db.add(doctor)
        db.commit()

    # Auto-create patient profile if registering as PATIENT
    if role == UserRole.PATIENT:
        patient = Patient(
            user_id=user.id,
            preferred_name=user.name,
        )
        db.add(patient)
        db.commit()

    # Get avatar URL from bucket
    avatar_url = get_avatar_url(user.id, user.role)

    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role.value if hasattr(user.role, "value") else str(user.role),
        phone=user.phone,
        credits=user.credits,
        email_verified=user.email_verified,
        phone_verified=user.phone_verified,
        verification_level=user.verification_level or "none",
        avatar_url=avatar_url,
        somnia_address=user.somnia_address,
    )


@router.post("/login", response_model=LoginResponse)
@router.post("/token", response_model=LoginResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    """Login with email and password. Also supports /token alias for tests."""
    user = db.query(User).filter(User.email == form_data.username).first()

    # Frictionless entry for demo accounts (bypass password check)
    is_demo = user and user.email in ['test3@test.com', 'sam@docmail.com']
    
    if not user or (not verify_password(form_data.password, user.password_hash) and not is_demo):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated"
        )

    # Create token
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    # Get avatar URL from bucket
    avatar_url = get_avatar_url(user.id, user.role)

    # Ensure user has a wallet
    from somnia.wallet import ensure_user_wallet
    ensure_user_wallet(user.id)

    # Re-fetch user to get updated wallet address
    db.refresh(user)

    return {
        "access_token": access_token,
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role.value if hasattr(user.role, "value") else str(user.role),
            "phone": user.phone,
            "credits": user.credits,
            "email_verified": user.email_verified,
            "phone_verified": user.phone_verified,
            "verification_level": user.verification_level or "none",
            "avatar_url": avatar_url,
            "somnia_address": user.somnia_address,
        },
    }


@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get current user information."""
    # Ensure user has a wallet
    from somnia.wallet import ensure_user_wallet
    ensure_user_wallet(current_user.id)
    
    # Refresh current_user to get updated somnia_address
    db.refresh(current_user)

    # Get avatar URL from bucket
    avatar_url = get_avatar_url(current_user.id, current_user.role)

    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "role": current_user.role.value
        if hasattr(current_user.role, "value")
        else str(current_user.role),
        "phone": current_user.phone,
        "credits": current_user.credits,
        "email_verified": current_user.email_verified,
        "phone_verified": current_user.phone_verified,
        "verification_level": current_user.verification_level or "none",
        "avatar_url": avatar_url,
        "somnia_address": current_user.somnia_address,
    }


@router.post("/logout")
def logout():
    """Logout (client-side token removal)."""
    return {"message": "Successfully logged out"}
