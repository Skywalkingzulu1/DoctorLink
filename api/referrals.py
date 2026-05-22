"""
Referral API endpoints for DoctorLink.
"""

import os
import sys
import random
import string

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict

from database import get_db, Referral, User
from auth import get_current_user

router = APIRouter(prefix="/api/referrals", tags=["referrals"])


class ReferralResponse(BaseModel):
    id: int
    referrer_id: int
    referee_id: int | None
    code: str
    status: str
    reward_credits: int
    created_at: str | None = None
    completed_at: str | None = None
    referee_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ReferralStatsResponse(BaseModel):
    total_referrals: int
    completed_referrals: int
    pending_referrals: int
    total_rewards: int
    referral_code: str | None = None
    referral_link: str | None = None


class UseReferralRequest(BaseModel):
    code: str


def generate_referral_code(length=8):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))


@router.post("/generate-code")
def generate_referral_code_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate a unique referral code for the current user."""
    existing = db.query(Referral).filter(Referral.referrer_id == current_user.id).first()
    if existing:
        return {"code": existing.code}

    code = generate_referral_code()
    while db.query(Referral).filter(Referral.code == code).first():
        code = generate_referral_code()

    referral = Referral(
        referrer_id=current_user.id,
        code=code,
    )
    db.add(referral)
    db.commit()
    db.refresh(referral)

    return {"code": referral.code}


@router.get("/my-code")
def get_my_referral_code(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current user's referral code and link."""
    referral = db.query(Referral).filter(Referral.referrer_id == current_user.id).first()
    if not referral:
        return {"code": None, "link": None}

    base_url = os.getenv("FRONTEND_URL", "https://skywalkingzulu1.github.io/DoctorLink")
    return {
        "code": referral.code,
        "link": f"{base_url}/register.html?ref={referral.code}",
    }


@router.post("/use-code")
def use_referral_code(
    request: UseReferralRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Use a referral code (link referee to referrer)."""
    if not request.code:
        raise HTTPException(status_code=400, detail="Referral code is required")

    referral = db.query(Referral).filter(Referral.code == request.code.upper()).first()
    if not referral:
        raise HTTPException(status_code=404, detail="Invalid referral code")

    if referral.referrer_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot use your own referral code")

    if referral.referee_id is not None:
        raise HTTPException(status_code=400, detail="Referral code already used")

    referral.referee_id = current_user.id
    referral.status = "completed"
    referral.completed_at = __import__("datetime").datetime.utcnow()

    # Credit referrer
    referrer = db.query(User).filter(User.id == referral.referrer_id).first()
    if referrer:
        referrer.credits = (referrer.credits or 0) + referral.reward_credits

    db.commit()

    return {
        "message": "Referral code applied! You and your referrer get bonus credits.",
        "reward_credits": referral.reward_credits,
    }


@router.get("/stats", response_model=ReferralStatsResponse)
def get_referral_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get referral statistics for the current user."""
    referrals = db.query(Referral).filter(Referral.referrer_id == current_user.id).all()
    completed = [r for r in referrals if r.status == "completed"]
    pending = [r for r in referrals if r.status == "pending"]

    referral_code = None
    if referrals:
        referral_code = referrals[0].code

    base_url = os.getenv("FRONTEND_URL", "https://skywalkingzulu1.github.io/DoctorLink")

    return ReferralStatsResponse(
        total_referrals=len(referrals),
        completed_referrals=len(completed),
        pending_referrals=len(pending),
        total_rewards=sum(r.reward_credits for r in completed),
        referral_code=referral_code,
        referral_link=f"{base_url}/register.html?ref={referral_code}" if referral_code else None,
    )


@router.get("", response_model=List[ReferralResponse])
def list_referrals(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all referrals made by the current user."""
    referrals = db.query(Referral).filter(Referral.referrer_id == current_user.id).all()

    result = []
    for r in referrals:
        data = Referral.model_validate(r).model_dump()
        data["created_at"] = r.created_at.isoformat() if r.created_at else None
        data["completed_at"] = r.completed_at.isoformat() if r.completed_at else None
        # Get referee name
        if r.referee_id:
            referee = db.query(User).filter(User.id == r.referee_id).first()
            data["referee_name"] = referee.name if referee else None
        else:
            data["referee_name"] = None
        result.append(data)
    return result
