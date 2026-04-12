#!/usr/bin/env python3
"""
FastAPI router for Review related endpoints.

All endpoints require JWT authentication; the token payload is injected
as `current_user` for use within the handlers.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator, ConfigDict
from sqlalchemy.orm import Session

# Project imports
try:
    from ..database import SessionLocal  # type: ignore
    from ..models import Review, Doctor  # type: ignore
    from ..auth import get_current_user  # type: ignore
except ImportError as e:
    raise ImportError(
        "Could not import required modules for reviews. Ensure `database.py`, `models.py`, and `auth.py` exist."
    ) from e

router = APIRouter(
    prefix="",
    tags=["reviews"],
    dependencies=[Depends(get_current_user)],
)

# ----------------------------------------------------------------------
# Dependency that provides a DB session
# ----------------------------------------------------------------------
def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ----------------------------------------------------------------------
# Pydantic schemas
# ----------------------------------------------------------------------
class ReviewBase(BaseModel):
    doctor_id: int
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None

    @field_validator("rating")
    @classmethod
    def rating_range(cls, v):
        if not (1 <= v <= 5):
            raise ValueError("Rating must be between 1 and 5")
        return v


class ReviewCreate(ReviewBase):
    pass


class ReviewUpdate(BaseModel):
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    comment: Optional[str] = None

    @field_validator("rating")
    @classmethod
    def rating_range(cls, v):
        if v is not None and not (1 <= v <= 5):
            raise ValueError("Rating must be between 1 and 5")
        return v


class ReviewResponse(ReviewBase):
    id: int
    user_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ----------------------------------------------------------------------
# Helper to extract user id from JWT payload
# ----------------------------------------------------------------------
def _get_user_id_from_token(payload: dict) -> int:
    """
    Extract the user identifier from the JWT payload.
    The payload is expected to contain an ``sub`` (subject) claim with the user id.
    Adjust this function if your token structure differs.
    """
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload missing 'sub' claim.",
        )
    try:
        return int(user_id)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user identifier in token.",
        )


# ----------------------------------------------------------------------
# CRUD Endpoints
# ----------------------------------------------------------------------
@router.get("/", response_model=None)
def list_reviews(
    doctor_id: Optional[int] = None,
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """
    Retrieve a list of reviews. Optional filters by ``doctor_id`` and/or ``user_id``.
    """
    query = db.query(Review)

    if doctor_id is not None:
        query = query.filter(Review.doctor_id == doctor_id)

    if user_id is not None:
        query = query.filter(Review.user_id == user_id)

    return query.all()


@router.post("/", response_model=None, status_code=status.HTTP_201_CREATED)
def create_review(
    review_in: ReviewCreate,
    payload: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new review. The authenticated user becomes the ``user_id`` of the review.
    """
    user_id = _get_user_id_from_token(payload)

    # Verify doctor exists
    doctor = db.query(Doctor).filter(Doctor.id == review_in.doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    # Optional: prevent duplicate reviews by same user for same doctor
    existing = (
        db.query(Review)
        .filter(Review.doctor_id == review_in.doctor_id, Review.user_id == user_id)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400, detail="You have already reviewed this doctor."
        )

    new_review = Review(
        doctor_id=review_in.doctor_id,
        user_id=user_id,
        rating=review_in.rating,
        comment=review_in.comment,
        created_at=datetime.utcnow(),
    )
    db.add(new_review)
    db.commit()
    db.refresh(new_review)
    return new_review


@router.get("/{review_id}", response_model=None)
def get_review(review_id: int, db: Session = Depends(get_db)):
    """
    Retrieve a single review by its ID.
    """
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return review


@router.put("/{review_id}", response_model=None)
def update_review(
    review_id: int,
    review_in: ReviewUpdate,
    payload: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update an existing review. Only the author of the review may modify it.
    """
    user_id = _get_user_id_from_token(payload)

    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    if review.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to modify this review.",
        )

    if review_in.rating is not None:
        review.rating = review_in.rating
    if review_in.comment is not None:
        review.comment = review_in.comment

    db.commit()
    db.refresh(review)
    return review


@router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_review(
    review_id: int,
    payload: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete a review. Only the author of the review may delete it.
    """
    user_id = _get_user_id_from_token(payload)

    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    if review.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to delete this review.",
        )

    db.delete(review)
    db.commit()
    return None
