#!/usr/bin/env python3
"""
Alembic‑style migration to create the `appointments` table.

If Alembic is not being used in the project, this script can be executed
directly (e.g. `python migrations/001_create_appointment.py`) to create
the table against the configured database.
"""

from sqlalchemy import (
    Table,
    Column,
    Integer,
    DateTime,
    Enum,
    ForeignKey,
    MetaData,
)
from sqlalchemy.engine import create_engine
import os

# Import the enum used by the model
from ..models import AppointmentStatus

# ----------------------------------------------------------------------
# Database connection (reuse the same URL as the main app)
# ----------------------------------------------------------------------
DATABASE_URL = os.getenv(
    "DATABASE_URL", "sqlite:///./doctorlink.db"
)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
    if DATABASE_URL.startswith("sqlite")
    else {},
)

metadata = MetaData()


def upgrade():
    """Create the appointments table."""
    appointments = Table(
        "appointments",
        metadata,
        Column("id", Integer, primary_key=True, index=True),
        Column("patient_id", Integer, ForeignKey("users.id"), nullable=False),
        Column("doctor_id", Integer, ForeignKey("doctors.id"), nullable=False),
        Column("timestamp", DateTime, nullable=False),
        Column(
            "status",
            Enum(AppointmentStatus),
            nullable=False,
            default=AppointmentStatus.SCHEDULED,
        ),
        Column("price_credits", Integer, nullable=False, default=0),
    )
    metadata.create_all(engine, tables=[appointments])
    print("✅ appointments table created.")


def downgrade():
    """Drop the appointments table."""
    appointments = Table("appointments", metadata, autoload_with=engine)
    appointments.drop(engine)
    print("🗑️ appointments table dropped.")


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2 or sys.argv[1] not in {"upgrade", "downgrade"}:
        print("Usage: python 001_create_appointment.py [upgrade|downgrade]")
        sys.exit(1)

    if sys.argv[1] == "upgrade":
        upgrade()
    else:
        downgrade()