#!/usr/bin/env python3
"""
FastAPI router for telehealth and real-time consultation updates.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import APIRouter, Depends, WebSocket, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime

from auth import get_current_user, require_role
from api.websocket_manager import manager
from database import (
    get_db,
    SessionLocal,
    RoomStatus,
    History,
    Appointment,
    AppointmentStatus,
    User,
    Doctor,
)
from config import settings

router = APIRouter(
    prefix="/api/telehealth",
    tags=["telehealth"],
)


class TeleconsultationStatusUpdate(BaseModel):
    status: RoomStatus


class SignalExchange(BaseModel):
    target_id: int
    signal_data: str  # JSON string of WebRTC offer/answer/ice-candidate


class MeetingSummary(BaseModel):
    appointment_id: int
    summary: str


@router.get("/ice-servers")
async def get_ice_servers(current_user: User = Depends(get_current_user)):
    """
    Returns the ICE server configuration (STUN/TURN) for WebRTC.
    """
    return {
        "iceServers": [
            {"urls": "stun:stun.l.google.com:19302"},
            {
                "urls": settings.TURN_SERVER_URL,
                "username": settings.TURN_SERVER_USER,
                "credential": settings.TURN_SERVER_PASSWORD,
            },
        ]
    }


@router.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: int):
    """
    WebSocket connection for a specific teleconsultation room.
    Clients connect to receive real-time status updates.
    """
    await manager.connect(websocket, room_id=room_id)
    try:
        while True:
            # Keep connection alive; ignore incoming messages
            await websocket.receive_text()
    except Exception:
        pass
    finally:
        manager.disconnect(websocket, room_id=room_id)


@router.post("/rooms/{room_id}/status")
async def update_room_status(
    room_id: int,
    update: TeleconsultationStatusUpdate,
    current_user: User = Depends(get_current_user),
):
    """
    Push a new status to all connected clients in the specified room.
    """
    await manager.broadcast(room_id, update.status.value)
    return {"room_id": room_id, "new_status": update.status.value}


@router.post("/rooms/{room_id}/signals")
async def exchange_signals(
    room_id: int,
    signal: SignalExchange,
    current_user: User = Depends(get_current_user),
):
    """
    Relays the WebRTC signal to the target user via WebSockets.
    """
    await manager.send_personal_message(
        {
            "type": "signal",
            "room_id": room_id,
            "sender_id": current_user.id,
            "signal_data": signal.signal_data,
        },
        signal.target_id,
    )
    return {"status": "signal_sent"}


@router.get("/history", response_model=None)
async def get_my_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get consultation history for the current user."""
    if current_user.role == "DOCTOR":
        doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
        if not doctor:
            return []
        records = db.query(History).filter(History.doctor_id == doctor.id).all()
    else:
        records = db.query(History).filter(History.patient_id == current_user.id).all()

    return records


@router.post("/summary", status_code=status.HTTP_201_CREATED)
async def post_summary(
    summary: MeetingSummary,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Doctor uploads meeting summary after consultation.
    """
    if current_user.role != "DOCTOR":
        raise HTTPException(status_code=403, detail="Only doctors can upload summaries")

    doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor profile not found")

    appointment = (
        db.query(Appointment).filter(Appointment.id == summary.appointment_id).first()
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if appointment.doctor_id != doctor.id:
        raise HTTPException(status_code=403, detail="Not your appointment")

    # Create history record
    history = History(
        appointment_id=appointment.id,
        patient_id=appointment.patient_id,
        doctor_id=doctor.id,
        visit_summary=summary.summary,
    )
    db.add(history)

    # Update appointment status
    appointment.status = AppointmentStatus.COMPLETED
    appointment.teleconsultation_status = RoomStatus.ENDED.value

    db.commit()
    db.refresh(history)

    return {"status": "summary_uploaded", "history_id": history.id}
