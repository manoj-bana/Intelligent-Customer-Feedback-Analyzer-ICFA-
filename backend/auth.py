from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from jose import jwt
import datetime
import re
import hashlib
 
from backend.database.db import SessionLocal
from backend.database.models import User
 
router = APIRouter()
 
SECRET_KEY = "icfa_secret_key"
ALGORITHM = "HS256"
 
 
# ======================
# Request Models
# ======================
 
class LoginRequest(BaseModel):
    username: str
    password: str
 
 
class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
<<<<<<< HEAD
    security_answers: str


=======
    security_question: str
    security_answer: str
 
class ForgotPasswordRequest(BaseModel):
    username: str
 
class VerifySecurityRequest(BaseModel):
    username: str
    answer: str
 
class ResetPasswordRequest(BaseModel):
    temp_token: str
    new_password: str
 
 
>>>>>>> afe831c8d0be1f66ee2d69a6708c99e0ddeb3ac2
# ======================
# Login API
# ======================
 
@router.post("/login")
def login(data: LoginRequest):
 
    db = SessionLocal()
 
    user = db.query(User).filter(User.username == data.username).first()
 
    if not user or user.password != data.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
 
    token = jwt.encode(
        {
            "sub": user.username,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=8)
        },
        SECRET_KEY,
        algorithm=ALGORITHM
    )
 
    return {"access_token": token, "username": user.username}
 
 
# ======================
# Register API
# ======================
 
@router.post("/register")
def register(data: RegisterRequest):
 
    db = SessionLocal()
 
    # Validation
    password_pattern = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$'
    email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
 
    if not re.match(email_pattern, data.email):
        raise HTTPException(status_code=400, detail="Invalid email format")
 
    existing_user = db.query(User).filter(User.username == data.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")
 
    existing_email = db.query(User).filter(User.email == data.email.lower()).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="Email already registered")
 
    if len(data.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be 8+ chars")
 
    if not re.match(password_pattern, data.password):
        raise HTTPException(
            status_code=400,
            detail="Password must have uppercase, lowercase, number, special char (@$!%*?&)"
        )
 
    if not data.security_question or not data.security_answer:
        raise HTTPException(status_code=400, detail="Security question and answer required")
 
    answer_hash = hashlib.sha256(data.security_answer.lower().encode()).hexdigest()
 
    # Save user
    new_user = User(
        username=data.username,
        email=data.email.lower(),
        password=data.password,
<<<<<<< HEAD
        security_answers=data.security_answers
=======
        security_question=data.security_question,
        security_answer_hash=answer_hash
>>>>>>> afe831c8d0be1f66ee2d69a6708c99e0ddeb3ac2
    )
 
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
 
    # Generate token
    token = jwt.encode(
        {
            "sub": new_user.username,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=8)
        },
        SECRET_KEY,
        algorithm=ALGORITHM
    )
 
    return {"access_token": token, "username": new_user.username}
 
 
@router.post("/forgot-password")
def forgot_password(data: ForgotPasswordRequest):
    db = SessionLocal()
    user = db.query(User).filter(User.username == data.username).first()
    db.close()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.security_question:
        raise HTTPException(status_code=400, detail="No security question set")
    return {"security_question": user.security_question}
 
 
@router.post("/verify-security-answer")
def verify_security(data: VerifySecurityRequest):
    db = SessionLocal()
    user = db.query(User).filter(User.username == data.username).first()
    db.close()
    if not user or not user.security_answer_hash:
        raise HTTPException(status_code=404, detail="User or security answer not found")
    provided_hash = hashlib.sha256(data.answer.lower().encode()).hexdigest()
    if provided_hash != user.security_answer_hash:
        raise HTTPException(status_code=401, detail="Incorrect security answer")
   
    # Issue temp token (15 min)
    temp_token = jwt.encode(
        {
            "sub": user.username,
            "type": "reset",
            "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=15)
        },
        SECRET_KEY,
        algorithm=ALGORITHM
    )
    return {"temp_token": temp_token}
 
 
@router.post("/reset-password")
def reset_password(data: ResetPasswordRequest):
    try:
        payload = jwt.decode(data.temp_token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload["sub"]
        if payload.get("type") != "reset":
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
   
    db = SessionLocal()
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
   
    # Validate new password
    password_pattern = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$'
    if len(data.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be 8+ chars")
    if not re.match(password_pattern, data.new_password):
        raise HTTPException(
            status_code=400,
            detail="Password must have uppercase, lowercase, number, special char (@$!%*?&)"
        )
   
    # Update password
    user.password = data.new_password
    db.commit()
    db.refresh(user)
    db.close()
    return {"success": True, "message": "Password updated successfully"}
 
 
# ======================
# Security Questions
# ======================

class SecQuestionsRequest(BaseModel):
    username: str

class SecVerifyRequest(BaseModel):
    username: str
    answers: str

@router.post("/get-security-questions")
def get_sec_questions(data: SecQuestionsRequest):
    db = SessionLocal()
    user = db.query(User).filter(User.username == data.username).first()
    db.close()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    questions = [
        "What was the name of your first pet?",
        "What is your mother's maiden name?",
        "What was the name of your first school?"
    ]
    return {"questions": questions}

@router.post("/verify-security")
def verify_sec(data: SecVerifyRequest):
    db = SessionLocal()
    user = db.query(User).filter(User.username == data.username).first()
    db.close()
    if not user or not user.security_answers:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if user.security_answers != data.answers:
        raise HTTPException(status_code=401, detail="Invalid security answers")
    token = jwt.encode(
        {
            "sub": user.username,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=8)
        },
        SECRET_KEY,
        algorithm=ALGORITHM
    )
    return {"access_token": token, "username": user.username}


# ======================
# Test API
# ======================
 
@router.get("/test")
def test():
    return {"message": "Auth route working with DB!"}
#.........