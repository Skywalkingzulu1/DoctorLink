#!/usr/bin/env python3
"""
Alembic migration script to create the `appointments` table.

This file assumes that Alembic is set up in the project. If Alembic is not
installed, you can still run the generated SQL manually against the
database.
"""

from alembic import op
import sqlalchemy as sa

# Revision identifiers, used by Alembic.
revision = "20231101_create_appointments"
down_revision = None  # Adjust if there are prior migrations.
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create appointments table with foreign keys to users and doctors."""
    op.create_table(
        "appointments",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("patient_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("doctor_id", sa.Integer, sa.ForeignKey("doctors.id"), nullable=False, index=True),
        sa.Column("timestamp", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("status", sa.String, nullable=False, server_default="scheduled"),
        sa.Column("price_credits", sa.Integer, nullable=False),
    )


def downgrade() -> None:
    """Drop the appointments table."""
    op.drop_table("appointments")