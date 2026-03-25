from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from jose import jwt
import datetime
import re
import secrets

import bcrypt

from backend.database.db import SessionLocal
from backend.database.models import User

router = APIRouter()
SECRET_KEY = "icfa_secret_key"
ALGORITHM = "HS256"


# ─── Password Hashing Utilities ───

def hash_password(plain: str) -> str:
    """Hash a plain-text password using bcrypt."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain-text password against its bcrypt hash."""
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def hash_answer(answer: str) -> str:
    """Hash a security answer (lowercased) using bcrypt."""
    return bcrypt.hashpw(answer.strip().lower().encode(), bcrypt.gensalt()).decode()


def verify_answer(plain: str, hashed: str) -> bool:
    """Verify a security answer against its bcrypt hash."""
    return bcrypt.checkpw(plain.strip().lower().encode(), hashed.encode())


def _make_token(username: str) -> str:
    return jwt.encode(
        {
            "sub": username,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=8),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


# ─── Pydantic Models ───

class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    security_question: str
    security_answer: str


# ─── Auth Routes ───

@router.post("/login")
def login(data: LoginRequest):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == data.username).first()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Support legacy plain-text passwords (migrated on first login)
        if user.password.startswith("$2b$") or user.password.startswith("$2a$"):
            # Bcrypt hash
            if not verify_password(data.password, user.password):
                raise HTTPException(status_code=401, detail="Invalid credentials")
        else:
            # Legacy plain-text — verify then upgrade to hash
            if user.password != data.password:
                raise HTTPException(status_code=401, detail="Invalid credentials")
            user.password = hash_password(data.password)
            db.commit()

        return {"access_token": _make_token(data.username), "username": data.username}
    finally:
        db.close()


@router.post("/register")
def register(data: RegisterRequest):
    password_pattern = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$'
    email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'

    if not re.match(email_pattern, data.email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    if not re.match(password_pattern, data.password):
        raise HTTPException(status_code=400, detail="Password must be 8+ chars with uppercase, lowercase, number, and special char (@$!%*?&)")
    if not data.security_question or not data.security_answer.strip():
        raise HTTPException(status_code=400, detail="Security question and answer required")

    db = SessionLocal()
    try:
        # Check duplicates via DB (single source of truth)
        if db.query(User).filter(User.username == data.username).first():
            raise HTTPException(status_code=400, detail="Username already exists")
        if db.query(User).filter(User.email == data.email.lower()).first():
            raise HTTPException(status_code=400, detail="Email already registered")

        new_user = User(
            username=data.username,
            email=data.email.lower(),
            password=hash_password(data.password),
            security_question=data.security_question,
            security_answer_hash=hash_answer(data.security_answer),
        )
        db.add(new_user)
        db.commit()
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"DB error: {e}")
    finally:
        db.close()

    return {"access_token": _make_token(data.username), "username": data.username}


# ─── Duplicate-check endpoints (used by frontend for real-time validation) ───

@router.get("/check-username")
def check_username(username: str):
    db = SessionLocal()
    try:
        exists = db.query(User).filter(User.username == username).first() is not None
        return {"exists": exists}
    finally:
        db.close()


@router.get("/check-email")
def check_email(email: str):
    db = SessionLocal()
    try:
        exists = db.query(User).filter(User.email == email.lower()).first() is not None
        return {"exists": exists}
    finally:
        db.close()


# ─── Forgot Password Routes ───

@router.post("/forgot-password")
def forgot_password(data: dict):
    username = data.get("username", "")
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return {"security_question": user.security_question}
    finally:
        db.close()


@router.post("/verify-security-answer")
def verify_security_answer(data: dict):
    username = data.get("username", "")
    answer = data.get("answer", "")
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Support legacy plain-text answers (migrated on first verify)
        stored = user.security_answer_hash or ""
        if stored.startswith("$2b$") or stored.startswith("$2a$"):
            if not verify_answer(answer, stored):
                raise HTTPException(status_code=401, detail="Wrong answer")
        else:
            # Legacy: plain lowercase comparison, then upgrade
            if stored != answer.strip().lower():
                raise HTTPException(status_code=401, detail="Wrong answer")
            user.security_answer_hash = hash_answer(answer)
            db.commit()

        # Store temp token against user for validation in reset step
        temp_token = secrets.token_urlsafe(32)
        user.reset_token = temp_token
        user.reset_token_expiry = str(
            datetime.datetime.utcnow() + datetime.timedelta(minutes=15)
        )
        db.commit()
        return {"temp_token": temp_token, "username": username}
    finally:
        db.close()


@router.post("/reset-password")
def reset_password(data: dict):
    temp_token = data.get("temp_token", "")
    username = data.get("username", "")
    new_password = data.get("new_password", "")

    password_pattern = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$'
    if not re.match(password_pattern, new_password):
        raise HTTPException(
            status_code=400,
            detail="Password must be 8+ chars with uppercase, lowercase, number, and special char",
        )

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user or user.reset_token != temp_token:
            raise HTTPException(status_code=401, detail="Invalid or expired reset token")

        # Check token expiry
        expiry = datetime.datetime.fromisoformat(user.reset_token_expiry)
        if datetime.datetime.utcnow() > expiry:
            raise HTTPException(status_code=401, detail="Reset token expired")

        user.password = hash_password(new_password)
        user.reset_token = None
        user.reset_token_expiry = None
        db.commit()
        return {"message": "Password reset successful"}
    finally:
        db.close()


@router.get("/test")
def test():
    return {"message": "Auth route working!"}
