# DoctorLink Code Review — Uncommitted Changes

**Review Date:** 2026-06-06  
**Working Tree:** `/root/DoctorLink` (16 modified files)

---

## Overall Assessment

The diff mixes **bug fixes**, **refactoring**, **new features**, and a **critical import regression**. Most changes are positive, but `api/reviews.py` has a likely runtime breakage, and `somnia/autonomous_agents.py` has a concurrency bug.

---

## 🔴 Critical Issues

### 1. `api/reviews.py` — Absolute imports will cause `ImportError`

The file no longer manipulates `sys.path` and now uses flat imports:

```python
from database import get_db, Review, Doctor
from auth import get_current_user
```

Every other `api/` module uses relative imports (`from ..database import ...`) or adds the project root to `sys.path`. If the CWD during startup is not `/root/DoctorLink`, this will fail. Apply the same `sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))` pattern used in `api/appointments.py`.

### 2. `somnia/autonomous_agents.py` — `AutonomousFollowUpScheduler` now busy-loops on first iteration

The duplicate `await asyncio.sleep(self.check_interval)` at the start of the `try` block was removed, but the one at the end remains. On the very first iteration, there is **no initial sleep**, meaning the agent immediately fires a full DB query + LLM pipeline on startup. While not a correctness bug, it defeats the purpose of `check_interval` as an initial cooldown and can spike resource usage at boot.

---

## 🟡 Moderate Issues

### 3. `somnia/autonomous_agents.py:248` — Variable referenced before assignment

```python
if appt.escrow_status == EscrowStatus.HELD or appt.somnia_tx_hash:
```

`appt.escrow_status` is evaluated first, which is fine, but the condition is logically loose. If `somnia_tx_hash` is set but `escrow_status` is something else (e.g. `RELEASED`), the escrow service may be called again. Consider using a flag like `needs_release` to prevent duplicate on-chain calls.

### 4. `main.py:417` — `sio.time()` replaced with `time.time()` is a semantic change

Socket.IO's `sio.time()` returns monotonic server uptime. `time.time()` returns Unix epoch. If the frontend uses these timestamps for relative message ordering within a room, switching to epoch time can break ordering (clock skew, NTP jumps). Verify the frontend consumes this as an absolute timestamp.

### 5. `filebase_db.py` — `setattr` behavior change

The indentation fix moves `setattr(inst, col.name, val)` inside the `if val is not None:` block. This means columns present in the dict but with `None` values will now be **skipped** entirely rather than being explicitly set to `None`. If downstream code distinguishes between "absent key" and "key present with None value," this could cause silent data loss. Confirm that `None` values are equivalent to "not provided" for all callers.

### 6. `api/auth.py:84-105` — Profile auto-creation uses minimally populated defaults

On idempotent register, a new `Doctor` gets `specialty="General Practitioner"` and a new `Patient` gets only `preferred_name`. If a real user partially completed a profile and then re-registers, they silently lose their progress. Consider merging rather than hard-creating, or preserving existing non-null fields.

---

## 🟢 Positive Fixes

| File | What was fixed |
|------|---------------|
| `api/appointments.py`, `auth.py`, `e2e_test.py`, `somnia/subscription.py`, `somnia/agent_service.py`, `api/referrals.py` | `datetime.utcnow()` → `datetime.now(timezone.utc)` — removes Python 3.12 deprecation warnings |
| `api/auth.py:208` | Fixed demo-login precedence so `is_demo` is evaluated **before** `verify_password`, preventing accidental lockout when a demo user changes their password hash |
| `api/storage.py` | Duplicate `upload_avatar` endpoint removed (already covered elsewhere or retired) |
| `api/somnia_agent.py` | Duplicate cost/response block in `invoke_stt_paid` removed |
| `api/reviews.py` | Removed custom `_get_user_id_from_token` shim; now uses `current_user.id` directly, which is the correct pattern |
| `somnia/autonomous_agents.py` | Removed duplicate `asyncio.sleep` in `AutonomousFollowUpScheduler`, fixing double-delay bug |

---

## 🟢 New Features

| File | Feature |
|------|---------|
| `database.py` | New `Review` model added |
| `api/reviews.py` | Response models added to all CRUD endpoints (`ReviewResponse`) |
| `api/auth.py` | Auto-creates `Doctor`/`Patient` profile on idempotent re-register |
| `seed_filebase.py` | AI Doctor demo seed added |

---

## ✓ Lint / Style Checks

```
api/referrals.py  — missing trailing newline
api/reviews.py    — missing trailing newline
```

Both files show `\ No newline at end of file` in the diff. This is non-functional but inconsistent with the rest of the codebase.
