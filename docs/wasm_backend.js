// DoctorLink Wasm Backend - Pyodide + SQLite
// This replaces the Python backend with WebAssembly

const WasmBackend = {
    pyodide: null,
    db: null,
    ready: false,
    readyPromise: null,

    async init() {
        if (this.readyPromise) return this.readyPromise;
        
        this.readyPromise = this._initPyodide();
        return this.readyPromise;
    },

    async _initPyodide() {
        try {
            this.pyodide = await loadPyodide();
            await this.pyodide.loadPackage("sqlite3");
            
            // Initialize database
            await this.pyodide.runPythonAsync(`
import sqlite3
import json
import base64
import os
import uuid
from datetime import datetime
import js

# Load persisted database or create new
stored_db = js.localStorage.getItem('dl_database')
if stored_db:
    import base64
    db_data = base64.b64decode(stored_db)
    with open('doctorlink.db', 'wb') as f:
        f.write(db_data)
    conn = sqlite3.connect('doctorlink.db')
else:
    conn = sqlite3.connect('doctorlink.db')

# Create tables
cursor = conn.cursor()

# Users/Profiles table
cursor.execute('''
CREATE TABLE IF NOT EXISTS profiles (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE,
    password TEXT,
    name TEXT,
    role TEXT CHECK(role IN ('PATIENT', 'DOCTOR')),
    credits INTEGER DEFAULT 0,
    wallet REAL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')

# Doctor profiles
cursor.execute('''
CREATE TABLE IF NOT EXISTS doctors (
    id TEXT PRIMARY KEY,
    user_id TEXT UNIQUE,
    specialty TEXT,
    qualification TEXT,
    experience INTEGER,
    bio TEXT,
    avatar_url TEXT,
    rating REAL DEFAULT 0,
    verification_level TEXT DEFAULT 'BASIC',
    price_basic INTEGER DEFAULT 200,
    price_standard INTEGER DEFAULT 350,
    price_premium INTEGER DEFAULT 500,
    price_emergency INTEGER DEFAULT 800,
    price_video INTEGER DEFAULT 400,
    is_online INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES profiles(id)
)
''')

# Appointments
cursor.execute('''
CREATE TABLE IF NOT EXISTS appointments (
    id TEXT PRIMARY KEY,
    patient_id TEXT,
    doctor_id TEXT,
    appointment_type TEXT,
    scheduled_time TEXT,
    status TEXT CHECK(status IN ('PENDING', 'CONFIRMED', 'COMPLETED', 'CANCELLED', 'EXPIRED')),
    credit_cost INTEGER,
    tip INTEGER DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES profiles(id),
    FOREIGN KEY (doctor_id) REFERENCES profiles(id)
)
''')

# Transactions
cursor.execute('''
CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    type TEXT CHECK(type IN ('CREDIT_PURCHASE', 'APPOINTMENT_PAYMENT', 'EARNING', 'TIP', 'WITHDRAWAL', 'REFUND')),
    amount INTEGER,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES profiles(id)
)
''')

# Prescriptions
cursor.execute('''
CREATE TABLE IF NOT EXISTS prescriptions (
    id TEXT PRIMARY KEY,
    appointment_id TEXT,
    doctor_id TEXT,
    patient_id TEXT,
    medication TEXT,
    dosage TEXT,
    instructions TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (appointment_id) REFERENCES appointments(id),
    FOREIGN KEY (doctor_id) REFERENCES profiles(id),
    FOREIGN KEY (patient_id) REFERENCES profiles(id)
)
''')

conn.commit()
print("Database initialized")
            `);
            
            this.ready = true;
            console.log("Wasm backend ready");
            return true;
        } catch (err) {
            console.error("Failed to init pyodide:", err);
            throw err;
        }
    },

    async save() {
        if (!this.pyodide) return;
        await this.pyodide.runPythonAsync(`
import base64
import js
with open('doctorlink.db', 'rb') as f:
    db_bytes = f.read()
js.localStorage.setItem('dl_database', base64.b64encode(db_bytes).decode())
print("Database saved")
        `);
    },

    // Auth operations
    async register(email, password, name, role = 'PATIENT') {
        await this.init();
        const id = 'user_' + Date.now();
        const credits = role === 'PATIENT' ? 500 : 0;
        
        const result = await this.pyodide.runPythonAsync(`
cursor = conn.cursor()
try:
    cursor.execute('INSERT INTO profiles (id, email, password, name, role, credits) VALUES (?, ?, ?, ?, ?, ?)',
        ['${id}', '${email}', '${btoa(password)}', '${name}', '${role}', ${credits}])
    conn.commit()
    # Create doctor profile if doctor
    ${role === 'DOCTOR' ? `
    cursor.execute('INSERT INTO doctors (id, user_id, specialty, qualification) VALUES (?, ?, ?, ?)',
        ['doc_${id}', '${id}', 'General Medicine', 'MD')
    conn.commit()
    ` : ''}
    print('OK')
except Exception as e:
    print('ERROR:' + str(e))
        `);
        
        await this.save();
        return this.signIn(email, password);
    },

    async signIn(email, password) {
        await this.init();
        const result = await this.pyodide.runPythonAsync(`
cursor = conn.cursor()
cursor.execute('SELECT id, email, name, role, credits, wallet FROM profiles WHERE email = ?', ['${email}'])
row = cursor.fetchone()
if row:
    stored_pass = row[2] if False else ''  # Skip password check for demo
    print('USER:' + json.dumps({'id': row[0], 'email': row[1], 'name': row[2], 'role': row[3], 'credits': row[4], 'wallet': row[5]}))
else:
    print('NOTFOUND')
        `);
        
        if (result.startsWith('USER:')) {
            const user = JSON.parse(result.substring(5));
            localStorage.setItem('dl_current_user', JSON.stringify(user));
            return { user, session: { access_token: 'demo_token_' + user.id } };
        }
        throw new Error('Invalid credentials');
    },

    async getDoctors() {
        await this.init();
        const result = await this.pyodide.runPythonAsync(`
cursor = conn.cursor()
cursor.execute('''
SELECT p.id, p.name, d.specialty, d.qualification, d.rating, d.verification_level,
       d.price_basic, d.price_standard, d.price_premium, d.price_emergency, d.price_video,
       d.is_online, d.avatar_url, d.bio
FROM doctors d JOIN profiles p ON d.user_id = p.id
WHERE d.is_online = 1
ORDER BY d.rating DESC
''')
rows = cursor.fetchall()
json.dumps([{
    'id': r[0], 'name': r[1], 'specialty': r[2], 'qualification': r[3],
    'rating': r[4], 'verification': r[5], 'price_basic': r[6],
    'price_standard': r[7], 'price_premium': r[8], 'price_emergency': r[9],
    'price_video': r[10], 'is_online': r[11], 'avatar': r[12], 'bio': r[13]
} for r in rows])
        `);
        return JSON.parse(result);
    },

    async getAppointments(userId) {
        await this.init();
        const result = await this.pyodide.runPythonAsync(`
cursor = conn.cursor()
cursor.execute('''
SELECT a.id, a.patient_id, a.doctor_id, a.appointment_type, a.scheduled_time,
       a.status, a.credit_cost, a.tip, a.notes, a.created_at,
       p.name as patient_name, d.specialty
FROM appointments a
LEFT JOIN profiles p ON a.patient_id = p.id
LEFT JOIN doctors d ON a.doctor_id = d.user_id
WHERE a.patient_id = '${userId}' OR a.doctor_id = '${userId}'
ORDER BY a.created_at DESC
''')
rows = cursor.fetchall()
json.dumps([{
    'id': r[0], 'patient_id': r[1], 'doctor_id': r[2], 'type': r[3],
    'time': r[4], 'status': r[5], 'cost': r[6], 'tip': r[7], 'notes': r[8],
    'created': r[9], 'patient_name': r[10], 'specialty': r[11]
} for r in rows])
        `);
        return JSON.parse(result);
    },

    async createAppointment(patientId, doctorId, type, time, cost) {
        await this.init();
        const id = 'appt_' + Date.now();
        
        await this.pyodide.runPythonAsync(`
cursor = conn.cursor()
cursor.execute('''INSERT INTO appointments 
    (id, patient_id, doctor_id, appointment_type, scheduled_time, status, credit_cost)
    VALUES (?, ?, ?, ?, ?, 'PENDING', ?)''',
    ['${id}', '${patientId}', '${doctorId}', '${type}', '${time}', ${cost}])
cursor.execute('UPDATE profiles SET credits = credits - ? WHERE id = ?', [${cost}, '${patientId}'])
conn.commit()
print('OK')
        `);
        
        await this.save();
        return { id, status: 'PENDING' };
    },

    async completeAppointment(appointmentId, doctorId) {
        await this.init();
        
        await this.pyodide.runPythonAsync(`
cursor = conn.cursor()
cursor.execute('SELECT credit_cost, tip FROM appointments WHERE id = ?', ['${appointmentId}'])
row = cursor.fetchone()
if row:
    total = row[0] + (row[1] or 0)
    doctor_earn = int(total * 0.8)
    cursor.execute('UPDATE appointments SET status = ?, completed_at = CURRENT_TIMESTAMP WHERE id = ?',
        ['COMPLETED', '${appointmentId}'])
    cursor.execute('UPDATE profiles SET wallet = wallet + ? WHERE id = ?', [doctor_earn, '${doctorId}'])
    conn.commit()
print('OK')
        `);
        
        await this.save();
        return { status: 'COMPLETED' };
    },

    async getTransactions(userId) {
        await this.init();
        const result = await this.pyodide.runPythonAsync(`
cursor = conn.cursor()
cursor.execute('''
SELECT id, type, amount, description, created_at
FROM transactions WHERE user_id = ?
ORDER BY created_at DESC LIMIT 20
''', ['${userId}'])
rows = cursor.fetchall()
json.dumps([{'id': r[0], 'type': r[1], 'amount': r[2], 'desc': r[3], 'time': r[4]} for r in rows])
        `);
        return JSON.parse(result);
    },

    async addCredits(userId, amount) {
        await this.init();
        await this.pyodide.runPythonAsync(`
cursor = conn.cursor()
cursor.execute('UPDATE profiles SET credits = credits + ? WHERE id = ?', [${amount}, '${userId}'])
cursor.execute('INSERT INTO transactions (id, user_id, type, amount, description) VALUES (?, ?, ?, ?, ?)',
    ['txn_${Date.now()}', '${userId}', 'CREDIT_PURCHASE', ${amount}, 'Credits purchased'])
conn.commit()
print('OK')
        `);
        await this.save();
    }
};

// Export for use
window.WasmBackend = WasmBackend;