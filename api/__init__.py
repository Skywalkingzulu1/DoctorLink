# API package for DoctorLink

from .auth import router as auth_router
from .doctors import router as doctors_router
from .appointments import router as appointments_router
from .prescriptions import router as prescriptions_router
from .records import router as records_router
from .credits import router as credits_router

__all__ = [
    "auth_router",
    "doctors_router",
    "appointments_router",
    "prescriptions_router",
    "records_router",
    "credits_router",
]
