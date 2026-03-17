from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from jose import jwt
import datetime
import re

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

@router.post("/login")
def login(data: LoginRequest):
    stored_password = USERS_DB.get(data.username)
    if not stored_password or stored_password != data.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = jwt.encode(
        {
            "sub": data.username,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=8)
        },
        SECRET_KEY,
        algorithm=ALGORITHM
    )
    return {"access_token": token, "username": data.username}

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


    # Store
    USERS_DB[data.username] = data.password
    EMAILS_DB.add(data.email.lower())

    # Return token like login
    token = jwt.encode(
        {
            "sub": data.username,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=8)
        },
        SECRET_KEY,
        algorithm=ALGORITHM
    )
    return {"access_token": token, "username": data.username}


@router.get("/test")
def test():
    return {"message": "Auth route working!"}
