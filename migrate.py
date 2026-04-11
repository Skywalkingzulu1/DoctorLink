#!/usr/bin/env python3
"""
Run database migrations (create tables) for DoctorLink.

This script uses SQLAlchemy's metadata to create all tables defined in
`models.py`. It works for both SQLite (default) and PostgreSQL (if the
`DATABASE_URL` environment variable points to a PostgreSQL instance).
"""

from .database import engine, Base

def run_migrations() -> None:
    """Create all tables in the database.

    The function is idempotent – calling it multiple times will not
    recreate existing tables.
    """
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    run_migrations()
