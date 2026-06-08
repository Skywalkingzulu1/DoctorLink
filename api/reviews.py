#!/usr/bin/env python3
"""
FastAPI router for Review related endpoints.

All endpoints require JWT authentication; the user is injected as current_user.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator, ConfigDict
from sqlalchemy.orm import Session

from database import get_db, Review, Doctor
from auth import get_current_user

router = APIRouter(
    prefix="/api/reviews",
    tags=["reviews"],
)


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


@router.get("/", response_model=list[ReviewResponse])
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


@router.post("/", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
def create_review(
    review_in: ReviewCreate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new review. The authenticated user becomes the ``user_id`` of the review.
    """
    # Verify doctor exists
    doctor = db.query(Doctor).filter(Doctor.id == review_in.doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    # Optional: prevent duplicate reviews by same user for same doctor
    existing = (
        db.query(Review)
        .filter(Review.doctor_id == review_in.doctor_id, Review.user_id == current_user.id)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400, detail="You have already reviewed this doctor."
        )

    new_review = Review(
        doctor_id=review_in.doctor_id,
        user_id=current_user.id,
        rating=review_in.rating,
        comment=review_in.comment,
        created_at=datetime.now(timezone.utc),
    )
    db.add(new_review)
    db.commit()
    db.refresh(new_review)
    return new_review


@router.get("/{review_id}", response_model=ReviewResponse)
def get_review(review_id: int, db: Session = Depends(get_db)):
    """
    Retrieve a single review by its ID.
    """
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return review


@router.put("/{review_id}", response_model=ReviewResponse)
def update_review(
    review_id: int,
    review_in: ReviewUpdate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update an existing review. Only the author of the review may modify it.
    """
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    if review.user_id != current_user.id:
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
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete a review. Only the author of the review may delete it.
    """
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    if review.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to delete this review.",
        )

    db.delete(review)
    db.commit()
    return None