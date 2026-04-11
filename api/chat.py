"""
Chat API for DoctorLink - persists chat messages.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List

from database import get_db, ChatMessage, User
from auth import get_current_user

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatMessageResponse(BaseModel):
    id: int
    appointment_id: int
    sender_id: int
    sender_name: str
    content: str
    created_at: str

    class Config:
        from_attributes = True


class ChatMessageCreate(BaseModel):
    content: str


@router.get("/{appointment_id}", response_model=List[ChatMessageResponse])
def get_chat_history(
    appointment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get chat history for an appointment."""
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.appointment_id == appointment_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )

    result = []
    for msg in messages:
        sender = db.query(User).filter(User.id == msg.sender_id).first()
        result.append(
            {
                "id": msg.id,
                "appointment_id": msg.appointment_id,
                "sender_id": msg.sender_id,
                "sender_name": sender.name if sender else "Unknown",
                "content": msg.content,
                "created_at": msg.created_at.isoformat() if msg.created_at else "",
            }
        )

    return result


@router.post("/{appointment_id}", response_model=ChatMessageResponse)
def send_chat_message(
    appointment_id: int,
    message: ChatMessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send a chat message (persisted to database)."""
    new_message = ChatMessage(
        appointment_id=appointment_id,
        sender_id=current_user.id,
        content=message.content,
    )
    db.add(new_message)
    db.commit()
    db.refresh(new_message)

    return {
        "id": new_message.id,
        "appointment_id": new_message.appointment_id,
        "sender_id": new_message.sender_id,
        "sender_name": current_user.name,
        "content": new_message.content,
        "created_at": new_message.created_at.isoformat()
        if new_message.created_at
        else "",
    }
