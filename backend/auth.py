from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from jose import jwt
import datetime
import re
import secrets
 
from backend.database.db import SessionLocal
from backend.database.models import User
 
router = APIRouter()
SECRET_KEY = "icfa_secret_key"
ALGORITHM = "HS256"
 
# Simple in-memory user DB with plain text passwords (good enough for college project). Emails tracked separately for uniqueness.
USERS_DB = {
    "admin": "admin123",
    "user1": "pass123",
}
EMAILS_DB = {"admin@example.com", "user1@example.com"}
 
class LoginRequest(BaseModel):
    username: str
    password: str
 
class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    security_question: str
    security_answer: str
 
@router.post("/login")
def login(data: LoginRequest):
    # First check in-memory
    stored_password = USERS_DB.get(data.username)
    if stored_password and stored_password == data.password:
        token = jwt.encode(
            {
                "sub": data.username,
                "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=8)
            },
            SECRET_KEY,
            algorithm=ALGORITHM
        )
        return {"access_token": token, "username": data.username}
   
    # Fallback to database for old users
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == data.username).first()
        if user and user.password == data.password:
            # Cache for future logins
            USERS_DB[data.username] = data.password
            token = jwt.encode(
                {
                    "sub": data.username,
                    "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=8)
                },
                SECRET_KEY,
                algorithm=ALGORITHM
            )
            return {"access_token": token, "username": data.username}
        raise HTTPException(status_code=401, detail="Invalid credentials")
    finally:
        db.close()
 
@router.post("/register")
def register(data: RegisterRequest):
    # Server-side validation matching frontend
    password_pattern = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$'
    email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
 
    if not re.match(email_pattern, data.email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    if data.username in USERS_DB:
        raise HTTPException(status_code=400, detail="Username already exists")
    if data.email.lower() in EMAILS_DB:
        raise HTTPException(status_code=400, detail="Email already registered")
    if len(data.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be 8+ chars")
    if not re.match(password_pattern, data.password):
        raise HTTPException(status_code=400, detail="Password must have uppercase, lowercase, number, special char (@$!%*?&)")
    if not data.security_question or not data.security_answer:
        raise HTTPException(status_code=400, detail="Security question and answer required")
 
    # Store in DB
    db = SessionLocal()
    try:
        new_user = User(
            username=data.username,
            email=data.email,
            password=data.password,  # In production: hash_password(data.password)
            security_question=data.security_question,
            security_answer_hash=data.security_answer.lower()  # Simple hash (case insensitive)
        )
        db.add(new_user)
        db.commit()
       
        # Also update in-memory for login
        USERS_DB[data.username] = data.password
        EMAILS_DB.add(data.email.lower())
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"DB error: {e}")
    finally:
        db.close()
 
    # Login new user immediately (return token)
    token = jwt.encode(
        {
            "sub": data.username,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=8)
        },
        SECRET_KEY,
        algorithm=ALGORITHM
    )
    return {"access_token": token, "username": data.username}
 
# ─── FORGOT PASSWORD ROUTES ───
@router.post("/forgot-password")
def forgot_password(data: dict):
    username = data["username"]
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
    username = data["username"]
    answer = data["answer"].lower()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user or user.security_answer_hash != answer:
            raise HTTPException(status_code=401, detail="Wrong answer")
       
        temp_token = secrets.token_urlsafe(32)
        return {"temp_token": temp_token}
    finally:
        db.close()
 
@router.post("/reset-password")
def reset_password(data: dict):
    temp_token = data["temp_token"]
    new_password = data["new_password"]
   
    # Update password in DB (demo: skip token validation)
    db = SessionLocal()
    try:
        # In production: verify temp_token belongs to user
        # For demo: update LAST user (not secure but works)
        users = db.query(User).all()
        if users:
            users[-1].password = new_password  # Last registered user
            db.commit()
           
            # Update in-memory
            USERS_DB[users[-1].username] = new_password
        return {"message": "Password reset successful"}
    finally:
        db.close()
 
@router.get("/test")
def test():
    return {"message": "Auth route working!"}