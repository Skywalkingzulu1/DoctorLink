import os
from supabase import create_client
from dotenv import load_dotenv

# Load production environment
load_dotenv()

def seed_database():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    supabase = create_client(url, key)
    
    print("--- SEEDING DOCTORLINK DATABASE ---")
    
    # 1. Create a System/Test Profile
    print("Seeding Profiles...")
    profile_data = {
        "id": 1, # Using bigint as discovered in audit
        "email": "system.admin@doctorlink.co.za",
        "name": "DoctorLink Admin",
        "role": "ADMIN",
        "credits": 1000
    }
    
    try:
        supabase.table("Profiles").upsert(profile_data).execute()
        print("✅ Profile seeded")
    except Exception as e:
        print(f"❌ Profile error: {e}")

    # 2. Create Test Doctors
    print("Seeding Doctors...")
    doctors = [
        {
            "id": 1,
            "user_id": 1,
            "name": "Dr. Sarah Zulu",
            "specialty": "General Practitioner",
            "area": "Johannesburg",
            "bio": "Experienced GP with 10+ years in telemedicine.",
            "rating": 4.9,
            "review_count": 124,
            "consultation_fee": 150,
            "is_online": True,
            "is_available": True,
            "quick_chat_price": 50,
            "video_call_price": 150,
            "full_consultation_price": 250
        },
        {
            "id": 2,
            "name": "Dr. Andile Khumalo",
            "specialty": "Pediatrician",
            "area": "Cape Town",
            "bio": "Specializing in child healthcare and nutrition.",
            "rating": 4.8,
            "review_count": 89,
            "consultation_fee": 200,
            "is_online": True,
            "is_available": True,
            "quick_chat_price": 70,
            "video_call_price": 200,
            "full_consultation_price": 350
        }
    ]
    
    for doc in doctors:
        try:
            supabase.table("Doctors").upsert(doc).execute()
            print(f"✅ Doctor '{doc['name']}' seeded")
        except Exception as e:
            print(f"❌ Doctor error ({doc['name']}): {e}")

    print("\n🚀 Seeding Complete! The platform now has active listings.")

if __name__ == "__main__":
    seed_database()
