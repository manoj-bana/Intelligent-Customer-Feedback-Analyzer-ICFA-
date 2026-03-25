# ICFA — Authentication Enhancement Summary

## Files Changed

| File | What changed |
|---|---|
| `backend/auth.py` | bcrypt hashing, real-time check endpoints, secure reset flow |
| `backend/database/models.py` | Added `reset_token` and `reset_token_expiry` columns |
| `frontend/register.py` | Real-time field validation, inline errors, password checklist |
| `frontend/login.py` | Improved forgot-password flow, password checklist on reset |
| `migrate_hashes.py` | One-time migration script for existing plain-text data |

---

## Deployment Steps

### 1. Install new dependency
```bash
pip install bcrypt
```

### 2. Replace files
Copy the three enhanced files over the originals:
```
backend/auth.py          → backend/auth.py
backend/database/models.py → backend/database/models.py
frontend/register.py     → frontend/register.py
frontend/login.py        → frontend/login.py
```

### 3. Migrate existing users (run once)
```bash
python migrate_hashes.py
```
This safely hashes any plain-text passwords and security answers already in
`icfa.db`. Already-hashed values are left untouched.

### 4. Restart the backend
```bash
uvicorn backend.main:app --reload --port 8000
```

---

## Feature Breakdown

### Username Validation
- On each keystroke the frontend calls `GET /auth/check-username?username=…`
- If taken: red inline message "Username already exists" appears immediately below the field
- Form submission is blocked until resolved

### Email Validation
- Format is checked client-side with a regex first
- Once the format is valid, `GET /auth/check-email?email=…` is called
- Inline messages: "Invalid email format" / "Email already registered" / green "Email available"

### Password Validation
- Live checklist beneath the password field (8+ chars, uppercase, lowercase, digit, special)
- Each rule shows ✅ / ❌ in real time as the user types
- "Confirm password" field shows inline match/mismatch status
- Same checklist appears in the Reset Password step

### Form Submission Handling
- On click, all fields are re-validated before the API is called
- Every failing field emits a distinct `st.error()` message
- Backend errors are mapped back to field-level hints (e.g. duplicate username sets the field red)

### Secure Data Storage — Passwords
- Passwords are hashed with **bcrypt** (`bcrypt.hashpw`) before INSERT
- Login uses `bcrypt.checkpw` for comparison — the plain text is never stored
- Legacy plain-text passwords in the DB are auto-upgraded to bcrypt on first successful login

### Secure Data Storage — Security Answers
- Security answers are normalised (stripped + lowercased) then **bcrypt-hashed** before storage
- Verification uses `bcrypt.checkpw`
- Legacy plain-text answers are upgraded on first successful verify

### Secure Reset Flow
- A `temp_token` (32-byte URL-safe random) is stored against the user row, together with a 15-minute expiry
- `/reset-password` validates the token AND the expiry before accepting the new password
- The token is cleared immediately after a successful reset
- The old implementation updated the *last registered user* — this is now fixed

### New API Endpoints
| Method | Path | Purpose |
|---|---|---|
| GET | `/auth/check-username?username=…` | Returns `{"exists": bool}` |
| GET | `/auth/check-email?email=…` | Returns `{"exists": bool}` |
