import os
from dotenv import load_dotenv

load_dotenv(".env")

from database import Base

def migrate_to_supabase():
    from config import settings
    print(f"Target Database: {settings.DATABASE_URL}")
    if "sqlite" in settings.DATABASE_URL:
        print("❌ CRITICAL: Settings still pointing to SQLite. Migration aborted.")
        return
    try:
        Base.metadata.create_all(bind=None)
        print("✅ Success: Schema migrated to Supabase")
    except Exception as e:
        print(f"❌ Error during migration: {e}")

if __name__ == "__main__":
    migrate_to_supabase()
