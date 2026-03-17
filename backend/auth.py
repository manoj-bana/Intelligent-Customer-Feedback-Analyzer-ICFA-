from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from jose import jwt
import datetime
import re

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

    # Save user
    new_user = User(
        username=data.username,
        email=data.email.lower(),
        password=data.password
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


# ======================
# Test API
# ======================

@router.get("/test")
def test():
    return {"message": "Auth route working with DB!"}