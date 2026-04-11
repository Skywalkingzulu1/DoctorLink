-- Supabase Database Setup for DoctorLink
-- Run this SQL in Supabase SQL Editor

-- ==================== PROFILES TABLE ====================
-- Extends Supabase auth.users with app-specific data
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT,
    name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('PATIENT', 'DOCTOR', 'ADMIN')) DEFAULT 'PATIENT',
    phone TEXT,
    credits INTEGER DEFAULT 0,
    avatar_url TEXT,
    email_verified BOOLEAN DEFAULT false,
    phone_verified BOOLEAN DEFAULT false,
    inconvenience_discount_amount INTEGER DEFAULT 0,
    inconvenience_discount_active BOOLEAN DEFAULT false,
    inconvenience_discount_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

-- Profile policies
CREATE POLICY "Users can view own profile" ON public.profiles
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update own profile" ON public.profiles
    FOR UPDATE USING (auth.uid() = id);

CREATE POLICY "Users can insert own profile" ON public.profiles
    FOR INSERT WITH CHECK (auth.uid() = id);

-- ==================== DOCTORS TABLE ====================
CREATE TABLE IF NOT EXISTS public.doctors (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    specialty TEXT DEFAULT 'General Practitioner',
    area TEXT DEFAULT '',
    bio TEXT,
    rating DECIMAL(3,2) DEFAULT 0,
    review_count INTEGER DEFAULT 0,
    consultation_fee INTEGER DEFAULT 150,
    is_available BOOLEAN DEFAULT true,
    is_online BOOLEAN DEFAULT false,
    hpcsa_number TEXT,
    verification_status TEXT DEFAULT 'pending',
    profile_completed BOOLEAN DEFAULT false,
    photo_url TEXT,
    -- Gig Economy Pricing
    quick_chat_price INTEGER DEFAULT 50,
    video_call_price INTEGER DEFAULT 150,
    full_consultation_price INTEGER DEFAULT 250,
    prescription_review_price INTEGER DEFAULT 80,
    report_analysis_price INTEGER DEFAULT 120,
    peak_pricing_multiplier DECIMAL(3,2) DEFAULT 1.0,
    gig_mode_enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE public.doctors ENABLE ROW LEVEL SECURITY;

-- Doctor policies
CREATE POLICY "Anyone can view doctors" ON public.doctors
    FOR SELECT USING (true);

CREATE POLICY "Doctors can update own profile" ON public.doctors
    FOR UPDATE USING (auth.uid() = user_id);

-- ==================== APPOINTMENTS TABLE ====================
CREATE TABLE IF NOT EXISTS public.appointments (
    id SERIAL PRIMARY KEY,
    patient_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
    doctor_id INTEGER REFERENCES public.doctors(id) ON DELETE CASCADE,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    appointment_type TEXT DEFAULT 'VIDEO',
    status TEXT DEFAULT 'SCHEDULED' CHECK (status IN ('SCHEDULED', 'CONFIRMED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED', 'NO_SHOW')),
    reason TEXT,
    notes TEXT,
    price_credits INTEGER DEFAULT 150,
    service_tier TEXT DEFAULT 'VIDEO_CALL',
    base_price INTEGER DEFAULT 150,
    platform_fee INTEGER DEFAULT 30,
    doctor_earnings INTEGER DEFAULT 120,
    tip_amount INTEGER DEFAULT 0,
    escrow_status TEXT DEFAULT 'PENDING' CHECK (escrow_status IN ('PENDING', 'ESCROWED', 'RELEASED', 'REFUNDED')),
    started_at TIMESTAMP WITH TIME ZONE,
    ended_at TIMESTAMP WITH TIME ZONE,
    duration_minutes INTEGER,
    report_url TEXT,
    prescription_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE public.appointments ENABLE ROW LEVEL SECURITY;

-- Appointment policies
CREATE POLICY "Patients can view own appointments" ON public.appointments
    FOR SELECT USING (auth.uid() = patient_id);

CREATE POLICY "Doctors can view own appointments" ON public.appointments
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.doctors 
            WHERE doctors.id = appointments.doctor_id 
            AND doctors.user_id = auth.uid()
        )
    );

CREATE POLICY "Patients can create appointments" ON public.appointments
    FOR INSERT WITH CHECK (auth.uid() = patient_id);

CREATE POLICY "Doctors can update own appointments" ON public.appointments
    FOR UPDATE USING (
        EXISTS (
            SELECT 1 FROM public.doctors 
            WHERE doctors.id = appointments.doctor_id 
            AND doctors.user_id = auth.uid()
        )
    );

-- ==================== PRESCRIPTIONS TABLE ====================
CREATE TABLE IF NOT EXISTS public.prescriptions (
    id SERIAL PRIMARY KEY,
    appointment_id INTEGER REFERENCES public.appointments(id) ON DELETE CASCADE,
    patient_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
    doctor_id INTEGER REFERENCES public.doctors(id) ON DELETE SET NULL,
    medication TEXT NOT NULL,
    dosage TEXT NOT NULL,
    instructions TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE public.prescriptions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Patient can view own prescriptions" ON public.prescriptions
    FOR SELECT USING (auth.uid() = patient_id);

CREATE POLICY "Doctor can manage prescriptions" ON public.prescriptions
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM public.doctors 
            WHERE doctors.id = prescriptions.doctor_id 
            AND doctors.user_id = auth.uid()
        )
    );

-- ==================== TIPS TABLE ====================
CREATE TABLE IF NOT EXISTS public.tips (
    id SERIAL PRIMARY KEY,
    appointment_id INTEGER REFERENCES public.appointments(id) ON DELETE CASCADE,
    patient_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
    doctor_id INTEGER REFERENCES public.doctors(id) ON DELETE SET NULL,
    amount INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE public.tips ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Patient can view own tips" ON public.tips
    FOR SELECT USING (auth.uid() = patient_id);

-- ==================== SERVICE TIER ENUM ====================
COMMENT ON COLUMN public.appointments.service_tier IS 'QUICK_CHAT, VIDEO_CALL, FULL_CONSULTATION, PRESCRIPTION_REVIEW, REPORT_ANALYSIS';

-- ==================== INDEXES ====================
CREATE INDEX IF NOT EXISTS idx_appointments_patient ON public.appointments(patient_id);
CREATE INDEX IF NOT EXISTS idx_appointments_doctor ON public.doctors(id);
CREATE INDEX IF NOT EXISTS idx_appointments_timestamp ON public.appointments(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_doctors_user_id ON public.doctors(user_id);
CREATE INDEX IF NOT EXISTS idx_doctors_online ON public.doctors(is_online) WHERE is_online = true;
CREATE INDEX IF NOT EXISTS idx_profiles_role ON public.profiles(role);

-- ==================== TRIGGER FOR AUTO-PROFILE ====================
-- Create profile automatically when user signs up
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, email, name, role, credits)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'name', split_part(NEW.email, '@', 1)),
        COALESCE(NEW.raw_user_meta_data->>'role', 'PATIENT'),
        CASE 
            WHEN COALESCE(NEW.raw_user_meta_data->>'role', 'PATIENT') = 'PATIENT' THEN 500
            ELSE 0
        END
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Drop existing trigger if exists
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;

-- Create trigger
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ==================== SEED DATA ====================
-- Insert sample doctors (run manually if needed)
-- INSERT INTO public.doctors (user_id, name, specialty, area, is_online) 
-- VALUES ('uuid-here', 'Dr. Smith', 'General Practitioner', 'Johannesburg', true);

SELECT 'DoctorLink tables created successfully!' as status;