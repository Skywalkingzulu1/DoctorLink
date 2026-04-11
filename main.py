"""
DoctorLink FastAPI Server with WebSocket Signaling.
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings
from database import init_db

# Import routers
from api.auth import router as auth_router
from api.doctors import router as doctors_router
from api.appointments import router as appointments_router
from api.prescriptions import router as prescriptions_router
from api.records import router as records_router
from api.credits import router as credits_router
from api.profile import router as profile_router
from api.availability import router as availability_router
from api.waiting_room import router as waiting_room_router
from api.chat import router as chat_router
from api.tips import router as tips_router
from api.storage import router as storage_router, ensure_bucket_exists
from api.telehealth import router as telehealth_router

# Create SocketIO server
sio = socketio.AsyncServer(
    cors_allowed_origins="*",
    async_mode="asgi",
    ping_timeout=60,
    ping_interval=25,
)

# Create FastAPI app
app = FastAPI(
    title="DoctorLink API",
    description="South Africa's Healthcare Platform API",
    version="1.0.0",
)

# Wrap SocketIO with ASGI
socket_app = socketio.ASGIApp(sio, app)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router, prefix="")
app.include_router(doctors_router, prefix="")
app.include_router(appointments_router, prefix="")
app.include_router(prescriptions_router, prefix="")
app.include_router(records_router, prefix="")
app.include_router(credits_router, prefix="")
app.include_router(profile_router, prefix="")
app.include_router(availability_router, prefix="")
app.include_router(waiting_room_router, prefix="")
app.include_router(chat_router, prefix="")
app.include_router(tips_router, prefix="")
app.include_router(telehealth_router, prefix="")
app.include_router(storage_router, prefix="/api/storage")


@app.on_event("startup")
def startup_event():
    """Initialize database and storage on startup."""
    init_db()
    ensure_bucket_exists()


@app.get("/")
def root():
    from fastapi.responses import RedirectResponse

    return RedirectResponse("/static/index_v2.html")


@app.get("/index.html")
def index_html():
    from fastapi.responses import RedirectResponse

    return RedirectResponse("/static/index.html")


@app.get("/doctor_dashboard.html")
def doctor_dashboard():
    from fastapi.responses import RedirectResponse

    return RedirectResponse("/static/doctor_dashboard.html")


@app.get("/health")
def health_check():
    return {"status": "healthy", "websocket": "connected"}


# Serve static files
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# ========== SIGNALING SERVER ==========

# Room management: {appointment_id: {sid: user_info}}
rooms = {}


@sio.event
async def connect(sid, environ, auth=None):
    """Client connected to signaling server."""
    print(f"Client connected: {sid}")
    query_string = environ.get("QUERY_STRING", "")
    rooms[sid] = {"authenticated": False, "user": None}
    await sio.emit("connected", {"sid": sid}, to=sid)


@sio.event
async def disconnect(sid):
    """Client disconnected."""
    print(f"Client disconnected: {sid}")
    for room_id, participants in list(rooms.items()):
        if isinstance(participants, dict) and sid in participants:
            del rooms[room_id][sid]
            await sio.emit("peer_left", {"sid": sid}, to=room_id)
    if sid in rooms:
        del rooms[sid]


@sio.event
async def authenticate(sid, data):
    """Authenticate user with JWT token."""
    token = data.get("token")
    if not token:
        await sio.emit("auth_error", {"message": "No token provided"}, to=sid)
        return

    try:
        from auth import verify_token
        from database import get_db, User

        payload = verify_token(token)
        if not payload:
            await sio.emit("auth_error", {"message": "Invalid token"}, to=sid)
            return

        user_id = int(payload.get("sub"))
        db = next(get_db())
        user = db.query(User).filter(User.id == user_id).first()

        if not user:
            await sio.emit("auth_error", {"message": "User not found"}, to=sid)
            return

        if sid in rooms:
            rooms[sid]["authenticated"] = True
            rooms[sid]["user"] = {
                "id": user.id,
                "name": user.name,
                "role": user.role.value,
            }

        await sio.emit(
            "authenticated", {"user_id": user.id, "role": user.role.value}, to=sid
        )

    except Exception as e:
        print(f"Auth error: {e}")
        await sio.emit("auth_error", {"message": str(e)}, to=sid)


@sio.event
async def join_room(sid, data):
    """Join a video call room (appointment) with security verification."""
    appointment_id = data.get("appointment_id")

    if not appointment_id:
        await sio.emit("error", {"message": "No appointment_id"}, to=sid)
        return

    if not rooms.get(sid, {}).get("authenticated"):
        await sio.emit("error", {"message": "Not authenticated"}, to=sid)
        return

    # SECURITY FIX: Verify appointment ownership
    try:
        from database import get_db, Appointment, User, Doctor

        db = next(get_db())
        user_info = rooms[sid].get("user", {})
        user_id = user_info.get("id")

        # Get the appointment
        appointment = (
            db.query(Appointment).filter(Appointment.id == appointment_id).first()
        )

        if not appointment:
            await sio.emit("error", {"message": "Appointment not found"}, to=sid)
            return

        # Verify user is either the patient or the doctor of this appointment
        is_patient = appointment.patient_id == user_id

        # Check if user is the doctor
        is_doctor = False
        doctor = db.query(Doctor).filter(Doctor.user_id == user_id).first()
        if doctor and appointment.doctor_id == doctor.id:
            is_doctor = True

        if not is_patient and not is_doctor:
            await sio.emit(
                "error", {"message": "Access denied - not your appointment"}, to=sid
            )
            return

        # Check appointment status (only allow joining for ACTIVE appointments)
        if appointment.status.value != "ACTIVE":
            await sio.emit(
                "error",
                {"message": f"Cannot join - appointment is {appointment.status.value}"},
                to=sid,
            )
            return

    except Exception as e:
        print(f"Error verifying appointment: {e}")
        await sio.emit("error", {"message": "Verification failed"}, to=sid)
        return

    # Proceed to join room
    await sio.enter_room(sid, str(appointment_id))

    room_id = str(appointment_id)
    if room_id not in rooms:
        rooms[room_id] = {}
    rooms[room_id][sid] = rooms[sid].get("user", {})

    other_participants = []
    for other_sid, info in rooms[room_id].items():
        if other_sid != sid and info:
            other_participants.append(
                {
                    "sid": other_sid,
                    "name": info.get("name", "Participant"),
                }
            )

    await sio.emit(
        "room_joined",
        {"appointment_id": appointment_id, "participants": other_participants},
        to=sid,
    )

    user_info = rooms[sid].get("user", {})
    await sio.emit(
        "peer_joined",
        {
            "sid": sid,
            "name": user_info.get("name", "Participant"),
        },
        to=room_id,
        skip_sid=sid,
    )

    print(f"User {sid} joined room {appointment_id}")


@sio.event
async def leave_room(sid, data):
    """Leave a video call room."""
    appointment_id = data.get("appointment_id")

    if appointment_id:
        room_id = str(appointment_id)
        await sio.leave_room(sid, room_id)

        if room_id in rooms and sid in rooms[room_id]:
            del rooms[room_id][sid]

        await sio.emit("peer_left", {"sid": sid}, to=room_id)
        print(f"User {sid} left room {appointment_id}")


@sio.event
async def offer(sid, data):
    """WebRTC offer - forward to specific peer."""
    target_sid = data.get("target_sid")
    offer_data = data.get("offer")
    appointment_id = data.get("appointment_id")

    if target_sid and offer_data:
        await sio.emit(
            "offer",
            {
                "offer": offer_data,
                "from_sid": sid,
                "appointment_id": appointment_id,
            },
            to=target_sid,
        )


@sio.event
async def answer(sid, data):
    """WebRTC answer - forward to specific peer."""
    target_sid = data.get("target_sid")
    answer_data = data.get("answer")
    appointment_id = data.get("appointment_id")

    if target_sid and answer_data:
        await sio.emit(
            "answer",
            {
                "answer": answer_data,
                "from_sid": sid,
                "appointment_id": appointment_id,
            },
            to=target_sid,
        )


@sio.event
async def ice_candidate(sid, data):
    """WebRTC ICE candidate - forward to specific peer."""
    target_sid = data.get("target_sid")
    candidate = data.get("candidate")
    appointment_id = data.get("appointment_id")

    if target_sid and candidate:
        await sio.emit(
            "ice_candidate",
            {
                "candidate": candidate,
                "from_sid": sid,
                "appointment_id": appointment_id,
            },
            to=target_sid,
        )


@sio.event
async def chat_message(sid, data):
    """Real-time chat message in call."""
    appointment_id = data.get("appointment_id")
    message = data.get("message")

    user_info = rooms.get(sid, {}).get("user", {})

    await sio.emit(
        "chat_message",
        {
            "message": message,
            "sender": user_info.get("name", "Participant"),
            "sender_id": user_info.get("id"),
            "timestamp": str(int(sio.time()) * 1000),
        },
        to=str(appointment_id),
    )


@sio.event
async def call_started(sid, data):
    """Doctor starts call with patient."""
    appointment_id = data.get("appointment_id")
    await sio.emit(
        "call_started", {"appointment_id": appointment_id}, to=str(appointment_id)
    )


@sio.event
async def call_ended(sid, data):
    """Call ended."""
    appointment_id = data.get("appointment_id")
    await sio.emit(
        "call_ended", {"appointment_id": appointment_id}, to=str(appointment_id)
    )


# Mount SocketIO app
app.mount("/socket.io", socket_app)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(socket_app, host="0.0.0.0", port=3000)
