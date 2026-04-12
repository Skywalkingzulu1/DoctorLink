import os
from dotenv import load_dotenv

# Load ENV first
load_dotenv(".env")

# Now import the engine which reads from settings (which reads from ENV)
from database import engine, Base

def migrate_to_supabase():
    # Force check the URL
    from config import settings
    print(f"Target Database: {settings.DATABASE_URL}")
    if "sqlite" in settings.DATABASE_URL:
        print("❌ CRITICAL: Settings still pointing to SQLite. Migration aborted.")
        return
    try:
        # Create all tables defined in models
        Base.metadata.create_all(bind=engine)
        print("✅ Success: Schema migrated to Supabase")
    except Exception as e:
        print(f"❌ Error during migration: {e}")

if __name__ == "__main__":
    migrate_to_supabase()
