"""
Auth API endpoints for DoctorLink.
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
from pydantic import BaseModel, EmailStr
import boto3
from botocore.config import Config

from database import get_db, User, UserRole, Doctor
from auth import hash_password, verify_password, create_access_token, get_current_user
from config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Filebase config
FILEBASE_BUCKET = "skyhealth"
FILEBASE_ENDPOINT = "https://s3.filebase.com"

# Lazy-loaded S3 client
_s3_client = None


def _get_s3_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client(
            "s3",
            endpoint_url=FILEBASE_ENDPOINT,
            aws_access_key_id=os.getenv("FILEBASE_ACCESS_KEY"),
            aws_secret_access_key=os.getenv("FILEBASE_SECRET_KEY"),
            config=Config(region_name="us-east-1", signature_version="s3v4"),
        )
    return _s3_client


def get_avatar_url(user_id: int, role: str = "PATIENT") -> str | None:
    """Get avatar URL from Filebase bucket if exists."""
    key = f"avatars/{user_id}.jpg"
    try:
        s3 = _get_s3_client()
        s3.head_object(Bucket=FILEBASE_BUCKET, Key=key)
        return f"{FILEBASE_ENDPOINT}/{FILEBASE_BUCKET}/{key}"
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

    class Config:
        from_attributes = True


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
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user."""
    # Check if email exists
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
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
        is_deleted=False,
        email_verified=True,  # Auto-verify for now
    )
    db.add(user)
    db.commit()
    db.refresh(user)

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
    )


@router.post("/login", response_model=LoginResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    """Login with email and password."""
    user = db.query(User).filter(User.email == form_data.username).first()

    if not user or not verify_password(form_data.password, user.password_hash):
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
        },
    }


@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information."""
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
    }


@router.post("/logout")
def logout():
    """Logout (client-side token removal)."""
    return {"message": "Successfully logged out"}
