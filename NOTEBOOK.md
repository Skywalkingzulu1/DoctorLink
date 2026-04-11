# DoctorLink - Final Development Notebook

## Wasm Backend Migration - IN PROGRESS

---

## Current Approach: WebAssembly + SQLite

Instead of using Supabase (which requires backend setup), we're using Pyodide (Python in WebAssembly) to run SQLite directly in the browser.

### Files Updated
- `docs/wasm_backend.js` - Pyodide-based SQLite backend
- `docs/index.html` - Updated to use Wasm backend instead of API calls
- `docs/supabase.js` - Deprecated (replaced by wasm_backend.js)

### How It Works
1. Pyodide loads Python + SQLite in the browser
2. Database stored in localStorage (persists across sessions)
3. All CRUD operations handled via JavaScript calling Python functions
4. Works completely offline after initial load

### Test Credentials
- Register a new account (500 credits for patients, 0 for doctors)

---

## Features Working

| Feature | Status |
|---------|--------|
| Patient Registration + 500 credits | ✅ |
| Doctor Registration + auto-profile | ✅ |
| View Doctors | ✅ |
| Book Appointment | ✅ |
| Credit Deduction | ✅ |
| View Appointments | ✅ |

---

## Running the App

```bash
# Just open docs/index.html in a browser
# No server needed - works entirely in browser
```