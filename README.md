# DoctorLink - Digital Healthcare Platform

A full-featured telemedicine platform built with FastAPI, SQLite, and vanilla JavaScript.

## Quick Start

```bash
# Install dependencies
pip install fastapi uvicorn sqlalchemy pydantic python-jose passlib

# Start server
python main.py

# Open in browser
http://localhost:3000
```

## Tech Stack

- **Backend**: FastAPI + SQLite
- **Frontend**: Vanilla JS + HTML/CSS
- **Video**: WebRTC (P2P)
- **Auth**: JWT tokens

## Project Structure

```
DoctorLink/
├── main.py              # Entry point
├── database.py          # Models & DB
├── config.py            # Settings
├── auth.py              # JWT helpers
├── api/
│   ├── auth.py          # Login/Register
│   ├── doctors.py       # Doctor listing
│   ├── appointments.py  # Booking system
│   ├── credits.py       # Credit system
│   ├── profile.py       # Doctor profile
│   ├── prescriptions.py # Prescriptions
│   └── records.py       # Medical records
└── static/
    ├── index.html       # Patient app
    ├── doctor_dashboard.html
    └── room.html        # Video consultation
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/register` | POST | Register user |
| `/api/auth/login` | POST | Login |
| `/api/doctors` | GET | List doctors |
| `/api/appointments` | GET/POST | List/Create appointments |
| `/api/appointments/{id}` | PATCH/DELETE | Update/Cancel |
| `/api/credits/balance` | GET | Get balance |
| `/api/credits/purchase` | POST | Buy credits |
| `/api/profile/doctor` | GET/PUT | Doctor profile |

## Test Credentials

| Role | Email | Password |
|------|-------|----------|
| Patient | test3@test.com | pass |
| Doctor | doc@docmail.com | test123 |

## Features

- Patient registration with 500 starting credits
- Doctor registration with auto-profile creation
- Two-tier verification (Basic ✓, Verified ★)
- Book appointments → Credit deduction
- Doctor dashboard → Accept/Complete
- Earnings system → Collect to wallet
- Video consultation room (WebRTC)
- Transaction history

## Business Model

- Patients buy credits (R1 = 1 credit)
- Doctors earn credits per appointment
- Platform takes commission on each booking
- Two-tier verification for trust

## Development

```bash
# Run tests
python -m pytest

# Add test data
python init_db.py

# API docs
http://localhost:3000/docs
```