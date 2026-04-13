# DoctorLink Platform Architecture Research

## Overview

This document outlines the three deployment platforms used in DoctorLink and how they fit together.

---

## 1. GitHub Pages (Static Hosting)

### What It Is
- Free static website hosting directly from a GitHub repository
- Serves files via CDN (fast global delivery)
- No server-side code execution

### Capabilities
| Feature | Supported | Notes |
|---------|-----------|-------|
| HTML/CSS/JS | ✅ | Full support |
| Client-side APIs | ✅ | Can call external APIs |
| User authentication | ⚠️ | Via external services (Firebase, Supabase, Auth0) |
| File uploads | ⚠️ | Can upload to external S3/Storage services |
| Forms with backend | ❌ | No server-side processing |
| Database access | ⚠️ | Via external APIs (REST/GraphQL) |

### Limitations
- No Python, Node.js, PHP, or any server-side code
- No WebSockets for real-time features
- No server-side secrets (API keys exposed in client code)
- 100MB max file size per file
- 1GB max site size

### Best Practices for DoctorLink
- Use for: Landing page, marketing content, waitlist forms
- Avoid: Any feature requiring backend processing
- Security: Encode sensitive keys (not secure for production), use env vars in production

### Current Usage
```
URL: https://skywalkingzulu1.github.io/DoctorLink/

Files served:
├── index.html          (Landing page)
├── static/
│   ├── waitlist_patient.html
│   ├── waitlist_doctor.html
│   └── filebase_upload.js  (Filebase direct upload)
└── docs/
    ├── index.html      (Main app with Wasm backend)
    └── wasm_backend.js
```

---

## 2. Railway (Full-Stack Deployment)

### What It Is
- Platform-as-a-Service (PaaS) for deploying full-stack applications
- Supports Python, Node.js, Go, Ruby, and more
- Automatic HTTPS, custom domains, CI/CD

### Capabilities
| Feature | Supported | Notes |
|---------|-----------|-------|
| FastAPI/Python | ✅ | Native support |
| WebSockets | ✅ | Socket.IO works |
| Database connections | ✅ | PostgreSQL, MySQL, etc. |
| Background workers | ✅ | Via Railway's worker tier |
| Cron jobs | ✅ | Via Third-party or worker |
| Custom domains | ✅ | Free SSL included |
| Environment variables | ✅ | Secure secret storage |

### Pricing
- **Free tier**: 500 hours/month, 1GB disk
- **Hobby**: $5/month, unlimited hours
- **Pro**: $20/month, more resources

### Best Practices for DoctorLink
- Use for: Full API backend, WebSocket server, database connections
- Store secrets in Railway env vars, not in code
- Use `.railwayignore` to exclude unnecessary files

### Current Usage
```
URL: https://andile-skywalkingzulu-production.up.railway.app/

Tech Stack:
├── main.py              (FastAPI + Socket.IO)
├── api/                 (All API endpoints)
│   ├── auth.py
│   ├── doctors.py
│   ├── appointments.py
│   └── ... (more)
├── waitlist_app.py      (Separate waitlist API)
├── database.py          (SQLite or Supabase PostgreSQL)
└── requirements.txt
```

---

## 3. Supabase (Backend-as-a-Service)

### What It Is
- Open-source Firebase alternative
- PostgreSQL database + Auth + Storage + Edge Functions

### Capabilities
| Feature | Supported | Notes |
|---------|-----------|-------|
| PostgreSQL | ✅ | Full relational DB |
| User Authentication | ✅ | Email, phone, OAuth |
| Row Level Security | ✅ | Fine-grained access control |
| File Storage | ✅ | S3-compatible |
| Edge Functions | ✅ | Deno/TypeScript serverless |
| Real-time subscriptions | ✅ | WebSocket-based |
| Auto-generated APIs | ✅ | REST + GraphQL |

### Current Config
```env
SUPABASE_URL=https://jvsfhrekkkhijneqngax.supabase.co
SUPABASE_ANON_KEY=sb_publishable_...
SUPABASE_SERVICE_KEY=eyJ... (admin access)
```

### Database Schema
```sql
-- Core tables
Profiles          (users: id, email, name, role, credits)
Doctors           (doctor profiles, pricing, verification)
appointments      (booking system with escrow)
prescriptions     (per appointment)
medical_records   (patient history)
transactions      (credits, payments)
tips              (doctor tips)
```

### Best Practices for DoctorLink
- Use Supabase Auth for user management
- Use RLS policies to secure data
- Use Edge Functions for sensitive API operations
- Consider Supabase Storage for file uploads instead of Filebase

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER (Browser)                               │
└─────────────────────────────────────────────────────────────────────┘
                                  │
              ┌───────────────────┴───────────────────┐
              │                                       │
              ▼                                       ▼
┌─────────────────────────┐             ┌─────────────────────────┐
│     GitHub Pages         │             │       Railway           │
│   (Static Only)          │             │   (Full Backend)        │
│                         │             │                         │
│ • Landing page          │             │ • /api/auth/*           │
│ • Waitlist forms        │             │ • /api/doctors/*        │
│ • Docs (Wasm app)       │             │ • /api/appointments/*   │
│                         │             │ • Socket.IO signals     │
│ Uses:                   │             │                         │
│ • Filebase (storage)    │             │ Uses:                   │
│ • External auth         │             │ • Supabase (database)   │
└─────────────────────────┘             │ • Supabase (auth)        │
                                       └─────────────────────────┘
                                                  │
                                                  ▼
                                       ┌─────────────────────────┐
                                       │       Supabase          │
                                       │                         │
                                       │ • PostgreSQL database   │
                                       │ • User authentication   │
                                       │ • Row Level Security    │
                                       │ • (Storage available)   │
                                       └─────────────────────────┘
```

---

## Data Flow Examples

### Waitlist Signup (GitHub Pages → Filebase)
```
1. User visits: https://skywalkingzulu1.github.io/DoctorLink/static/waitlist_patient.html
2. User fills form
3. JS calls: FilebaseUploader.uploadToFilebase()
4. AWS SDK uploads JSON to: skyhealth/waitlist/PATIENT/email_timestamp.json
5. User sees success message
```

### Login (Railway → Supabase)
```
1. User visits Railway app
2. POST /api/auth/login with email/password
3. Railway verifies against Supabase Auth
4. Returns JWT token
5. Subsequent requests use token for authorization
```

### Booking (Railway → Supabase)
```
1. Authenticated user POST /api/appointments
2. Railway validates JWT, checks credits
3. Railway inserts into Supabase (appointments table)
4. Returns appointment confirmation
```

---

## Decision Matrix

| Feature | GitHub Pages | Railway | Supabase |
|---------|--------------|---------|----------|
| Landing page | ✅ Best | ⚠️ Overkill | ❌ N/A |
| Waitlist forms | ✅ Works | ✅ Works | ⚠️ Extra setup |
| User auth | ⚠️ External | ✅ Full | ✅ Native |
| Appointments API | ❌ No | ✅ Full | ⚠️ Via Edge Fn |
| Database | ❌ No | ✅ Full | ✅ Native |
| Real-time (WebSocket) | ❌ No | ✅ Full | ✅ Native |
| File storage | ⚠️ Direct | ✅ Full | ✅ Native |
| Cost | Free | Free tier | Free tier |

---

## Recommendations

### Short Term (MVP)
1. **Keep GitHub Pages** for landing + waitlist (simplest)
2. **Keep Railway** for full API (all features work)
3. **Use Supabase** for database + auth (already set up)

### Long Term (Scale)
1. Consider moving waitlist to Railway → Supabase (more secure)
2. Add Supabase Storage for file uploads (replace Filebase)
3. Use Supabase Auth in both GitHub Pages and Railway
4. Consider Edge Functions for serverless API endpoints

---

## Security Notes

### GitHub Pages
- ❌ Never commit real API keys to JS files
- ⚠️ Encoding keys only provides obfuscation, not security
- ✅ Use environment variables in production

### Railway
- ✅ Use Railway env vars for secrets
- ✅ Never commit `.env` files
- ✅ Rotate secrets periodically

### Supabase
- ✅ Use anon key for client-side
- ✅ Use service key for server-side only
- ✅ Enable RLS on all tables
- ✅ Set up proper CORS policies

---

## Links

- GitHub Pages: https://pages.github.com
- Railway: https://railway.app
- Supabase: https://supabase.com

---

*Document generated: April 2026*
*Last updated: DoctorLink Architecture Research*