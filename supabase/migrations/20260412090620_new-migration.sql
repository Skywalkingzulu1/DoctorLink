-- DoctorLink Database Schema (Synced with existing Profiles.id BIGINT)

-- Profiles Table (Linked to Supabase Auth - using BIGINT as per existing live DB)
CREATE TABLE IF NOT EXISTS "Profiles" (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'PATIENT',
    credits INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Doctors Table
CREATE TABLE IF NOT EXISTS "Doctors" (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    user_id BIGINT REFERENCES "Profiles"(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    specialty TEXT NOT NULL,
    area TEXT NOT NULL,
    bio TEXT,
    rating FLOAT DEFAULT 4.5,
    review_count INTEGER DEFAULT 0,
    consultation_fee INTEGER DEFAULT 150,
    is_available BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    hpcsa_number TEXT,
    id_number TEXT,
    verification_status TEXT DEFAULT 'pending',
    profile_completed BOOLEAN DEFAULT FALSE,
    total_earnings INTEGER DEFAULT 0,
    pending_earnings INTEGER DEFAULT 0,
    quick_chat_price INTEGER DEFAULT 50,
    video_call_price INTEGER DEFAULT 150,
    full_consultation_price INTEGER DEFAULT 250,
    prescription_review_price INTEGER DEFAULT 80,
    report_analysis_price INTEGER DEFAULT 120,
    peak_pricing_multiplier FLOAT DEFAULT 1.0,
    is_online BOOLEAN DEFAULT TRUE,
    gig_mode_enabled BOOLEAN DEFAULT TRUE,
    hashgraph_account_id TEXT,
    photo_url TEXT
);

-- Appointments Table
CREATE TABLE IF NOT EXISTS appointments (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    patient_id BIGINT REFERENCES "Profiles"(id) ON DELETE CASCADE NOT NULL,
    doctor_id BIGINT REFERENCES "Doctors"(id) ON DELETE CASCADE NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    appointment_type TEXT DEFAULT 'VIDEO',
    status TEXT DEFAULT 'SCHEDULED',
    reason TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    price_credits INTEGER DEFAULT 150,
    teleconsultation_status TEXT DEFAULT 'pending',
    service_tier TEXT DEFAULT 'VIDEO_CALL',
    base_price INTEGER DEFAULT 150,
    platform_fee INTEGER DEFAULT 30,
    doctor_earnings INTEGER DEFAULT 120,
    tip_amount INTEGER DEFAULT 0,
    escrow_status TEXT DEFAULT 'PENDING',
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    duration_minutes INTEGER
);

-- Prescriptions Table
CREATE TABLE IF NOT EXISTS prescriptions (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    appointment_id BIGINT REFERENCES appointments(id) ON DELETE CASCADE NOT NULL,
    patient_id BIGINT REFERENCES "Profiles"(id) ON DELETE CASCADE NOT NULL,
    doctor_id BIGINT REFERENCES "Doctors"(id) ON DELETE CASCADE NOT NULL,
    medication TEXT NOT NULL,
    dosage TEXT NOT NULL,
    instructions TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Medical Records Table
CREATE TABLE IF NOT EXISTS medical_records (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    patient_id BIGINT REFERENCES "Profiles"(id) ON DELETE CASCADE NOT NULL,
    doctor_id BIGINT REFERENCES "Doctors"(id) ON DELETE CASCADE NOT NULL,
    appointment_id BIGINT REFERENCES appointments(id) ON DELETE SET NULL,
    summary TEXT NOT NULL,
    diagnosis TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Transactions Table
CREATE TABLE IF NOT EXISTS transactions (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    user_id BIGINT REFERENCES "Profiles"(id) ON DELETE CASCADE NOT NULL,
    amount INTEGER NOT NULL,
    transaction_type TEXT NOT NULL,
    description TEXT,
    payment_method TEXT,
    payment_status TEXT DEFAULT 'pending',
    payfast_payment_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tips Table
CREATE TABLE IF NOT EXISTS tips (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    appointment_id BIGINT REFERENCES appointments(id) ON DELETE CASCADE NOT NULL,
    patient_id BIGINT REFERENCES "Profiles"(id) ON DELETE CASCADE NOT NULL,
    doctor_id BIGINT REFERENCES "Doctors"(id) ON DELETE CASCADE NOT NULL,
    amount INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
