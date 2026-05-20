#!/usr/bin/env python3
"""
Run database migrations — no-op: Filebase document store has no schema.
"""

from database import Base

def run_migrations() -> None:
    print("Filebase document store: no schema migrations needed.")

if __name__ == "__main__":
    run_migrations()
