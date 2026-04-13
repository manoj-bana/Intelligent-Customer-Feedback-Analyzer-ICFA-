from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from jose import jwt
import datetime
import re
import secrets
import bcrypt
from backend.database.db import SessionLocal
from backend.database.models import User, AdminRequest, Notification, Organization

import os
from dotenv import load_dotenv

# Robust .env loading - look for it in the project root relative to this file
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(env_path)

router = APIRouter()
SECRET_KEY = os.getenv("SECRET_KEY", "icfa_secret_key")
ALGORITHM = os.getenv("ALGORITHM", "HS256")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def get_current_user(token: str = Depends(oauth2_scheme)):
    """Dependency to get the current authenticated user from JWT."""
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except Exception:
        raise credentials_exception

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if user is None:
            raise credentials_exception
        if user.is_active == 0:
            raise HTTPException(status_code=403, detail="Account deactivated")
        return user
    finally:
        db.close()

def get_current_org(current_user: User = Depends(get_current_user)):
    """Dependency to get the organization associated with the current user."""
    if not current_user.org_id:
        raise HTTPException(status_code=403, detail="User is not associated with any organization")
    
    db = SessionLocal()
    try:
        org = db.query(Organization).filter(Organization.id == current_user.org_id).first()
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
        return org
    finally:
        db.close()

def hash_password(password: str) -> str:
    """Securely hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a hashed one, supporting legacy auto-upgrade."""
    try:
        # Check if it's a bcrypt hash (starts with $2b$)
        if hashed_password.startswith('$2b$'):
            return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
        # Fallback for legacy plain-text
        return plain_password == hashed_password
    except Exception:
        return False

def hash_answer(answer: str) -> str:
    """Normalize and hash a security answer."""
    normalized = answer.strip().lower()
    return bcrypt.hashpw(normalized.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_answer(plain_answer: str, hashed_answer: str) -> bool:
    """Verify a security answer against its hash."""
    try:
        normalized = plain_answer.strip().lower()
        if hashed_answer.startswith('$2b$'):
            return bcrypt.checkpw(normalized.encode('utf-8'), hashed_answer.encode('utf-8'))
        return normalized == hashed_answer.lower()
    except Exception:
        return False

class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    security_question: str
    security_answer: str

class ChangePasswordRequest(BaseModel):
    username: str
    old_password: str
    new_password: str

class AdminElevationRequest(BaseModel):
    username: str
    reason: str

def create_notification(db, user_id, message):
    notif = Notification(user_id=user_id, message=message, is_read=0)
    db.add(notif)
    db.commit()


# --- Endpoints ---

@router.get("/check-username")
def check_username(username: str = Query(...)):
    """Validates if a username profile exists."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        exists = user is not None
        return {"exists": exists}
    finally:
        db.close()

@router.get("/check-email")
def check_email(email: str = Query(...)):
    """Check if an email is already registered."""
    db = SessionLocal()
    try:
        email_normalized = email.lower()
        user = db.query(User).filter(User.email == email_normalized).first()
        exists = user is not None
        return {"exists": exists}
    finally:
        db.close()

@router.post("/login")
def login(data: LoginRequest):
    """Authenticate a user and return an access token."""
    print(f"[AUTH] Login attempt for: {data.username}")
    
    # 1. Database check
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == data.username).first()
        if not user:
            # Try case-insensitive fallback for username
            user = db.query(User).filter(User.username.ilike(data.username)).first()
            
        if user:
            print(f"[AUTH] User found in DB. Verifying password for {user.username}...")
            if verify_password(data.password, user.password):
                if user.is_active == 0:
                    print(f"[AUTH] Warning: User {user.username} is deactivated.")
                    raise HTTPException(status_code=403, detail="Account deactivated. Please contact support.")
                
                # Auto-upgrade legacy plain-text password
                if not user.password.startswith('$2b$'):
                    print(f"[AUTH] Upgrading password for {user.username} to bcrypt.")
                    user.password = hash_password(data.password)
                    db.commit()

                expiration = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
                token = jwt.encode(
                    {
                        "sub": user.username, 
                        "role": user.role, 
                        "org_id": user.org_id,
                        "exp": expiration
                    },
                    SECRET_KEY,
                    algorithm=ALGORITHM
                )
                print(f"[AUTH] Success: {user.username} logged in (Org: {user.org_id}).")
                return {"access_token": token, "username": user.username, "role": user.role, "org_id": user.org_id}
            else:
                print(f"[AUTH] Failed: Password mismatch for {user.username}.")
        else:
            print(f"[AUTH] Failed: User {data.username} not found.")

        raise HTTPException(status_code=401, detail="Invalid credentials")
    finally:
        db.close()

@router.post("/register")
def register(data: RegisterRequest):
    """Register a new user with secure hashing."""
    # Check if registration is allowed
    allow_reg = os.getenv("ALLOW_REGISTRATION", "True").lower() == "true"
    if not allow_reg:
        raise HTTPException(status_code=403, detail="Self-registration is currently disabled.")

    if not re.match(r"[^@]+@[^@]+\.[^@]+", data.email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    if len(data.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be 8+ chars")

    db = SessionLocal()
    try:
        if db.query(User).filter(User.username == data.username).first():
            raise HTTPException(status_code=400, detail="Username already exists")
        if db.query(User).filter(User.email == data.email.lower()).first():
            raise HTTPException(status_code=400, detail="Email already registered")

        new_user = User(
            username=data.username,
            email=data.email.lower(),
            password=hash_password(data.password),
            security_question=data.security_question,
            security_answer_hash=hash_answer(data.security_answer)
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        expiration = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
        token = jwt.encode(
            {"sub": data.username, "role": "user", "exp": expiration},
            SECRET_KEY,
            algorithm=ALGORITHM
        )
        return {"access_token": token, "username": data.username, "role": "user"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        db.close()

@router.post("/forgot-password")
def forgot_password(data: dict):
    """Identify a user and return their security question."""
    username = data.get("username")
    if not username:
        raise HTTPException(status_code=400, detail="Username required")

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
    """Verify security answer and issue a temporary reset token."""
    username = data.get("username")
    answer = data.get("answer")
    if not username or not answer:
        raise HTTPException(status_code=400, detail="Username and answer required")

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user or not verify_answer(answer, user.security_answer_hash):
            raise HTTPException(status_code=401, detail="Incorrect security answer")

        # Auto-upgrade legacy plain-text answer if verified
        if not user.security_answer_hash.startswith('$2b$'):
            user.security_answer_hash = hash_answer(answer)

        # Generate 15-minute reset token
        temp_token = secrets.token_urlsafe(32)
        user.reset_token = temp_token
        user.reset_token_expiry = (datetime.datetime.utcnow() + datetime.timedelta(minutes=15)).isoformat()
        db.commit()

        return {"temp_token": temp_token}
    finally:
        db.close()

@router.post("/reset-password")
def reset_password(data: dict):
    """Reset the user password using a valid temporary token."""
    temp_token = data.get("temp_token")
    new_password = data.get("new_password")
    if not temp_token or not new_password:
        raise HTTPException(status_code=400, detail="Token and new password required")

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.reset_token == temp_token).first()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid reset token")

        # Check expiry
        expiry = datetime.datetime.fromisoformat(user.reset_token_expiry)
        if datetime.datetime.utcnow() > expiry:
            user.reset_token = None
            user.reset_token_expiry = None
            db.commit()
            raise HTTPException(status_code=401, detail="Reset token expired")

        # Success - Update password and clear token
        user.password = hash_password(new_password)
        user.reset_token = None
        user.reset_token_expiry = None
        db.commit()

        return {"message": "Password reset successful"}
    finally:
        db.close()
@router.post("/change-password")
def change_password(data: ChangePasswordRequest):
    """Update user password after verifying the old one."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == data.username).first()
        if not user or not verify_password(data.old_password, user.password):
            raise HTTPException(status_code=401, detail="Incorrect old password")
            
        if len(data.new_password) < 8:
            raise HTTPException(status_code=400, detail="New password must be 8+ chars")
            
        user.password = hash_password(data.new_password)
        db.commit()
        return {"message": "Password updated successfully"}
    finally:
        db.close()

# --- Admin Feature Endpoints ---

@router.post("/request-admin")
def request_admin(data: AdminElevationRequest):
    """Submit a request for admin privileges."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == data.username).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Check if already has a pending request
        existing = db.query(AdminRequest).filter(
            AdminRequest.username == data.username, 
            AdminRequest.status == "pending"
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="A request is already pending")
            
        new_req = AdminRequest(
            user_id=user.id,
            username=data.username,
            reason=data.reason
        )
        db.add(new_req)
        db.commit()
        return {"message": "Request submitted successfully"}
    finally:
        db.close()

@router.get("/admin-requests")
def get_admin_requests(admin_username: str = Query(...)):
    """Fetch all admin elevation requests (Admin only)."""
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == admin_username).first()
        if not admin or admin.role != "admin":
            # For testing/demo fallback: allow if username is 'admin'
            if admin_username != "admin":
                raise HTTPException(status_code=403, detail="Not authorized")
        
        requests = db.query(AdminRequest).all()
        return {"requests": [
            {
                "id": r.id, 
                "username": r.username, 
                "reason": r.reason, 
                "status": r.status, 
                "created_at": r.created_at
            } for r in requests
        ]}
    finally:
        db.close()

@router.post("/admin-requests/{request_id}/approve")
def approve_admin_request(request_id: int, admin_username: str = Query(...)):
    """Approve a privilege elevation request."""
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == admin_username).first()
        if not admin or admin.role != "admin":
            if admin_username != "admin":
                raise HTTPException(status_code=403, detail="Not authorized")
        
        req = db.query(AdminRequest).filter(AdminRequest.id == request_id).first()
        if not req:
            raise HTTPException(status_code=404, detail="Request not found")
            
        user = db.query(User).filter(User.username == req.username).first()
        if user:
            user.role = "admin"
            create_notification(db, user.id, "🎉 Your admin request has been APPROVED! Please log out and back in to see changes.")
            
        req.status = "approved"
        db.commit()
        return {"message": f"Successfully elevated {req.username} to Admin"}
    finally:
        db.close()

@router.post("/admin-requests/{request_id}/reject")
def reject_admin_request(request_id: int, admin_username: str = Query(...)):
    """Reject a privilege elevation request."""
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == admin_username).first()
        if not admin or admin.role != "admin":
            if admin_username != "admin":
                raise HTTPException(status_code=403, detail="Not authorized")
        
        req = db.query(AdminRequest).filter(AdminRequest.id == request_id).first()
        if not req:
            raise HTTPException(status_code=404, detail="Request not found")
            
        user = db.query(User).filter(User.username == req.username).first()
        if user:
            create_notification(db, user.id, "⚠️ Your admin request was rejected. Contact the lead administrator for details.")
            
        req.status = "rejected"
        db.commit()
        return {"message": "Request rejected"}
    finally:
        db.close()

@router.get("/users")
def get_all_users(admin_username: str = Query(...)):
    """Fetch all registered users (Admin only)."""
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == admin_username).first()
        if not admin or admin.role != "admin":
            if admin_username != "admin":
                raise HTTPException(status_code=403, detail="Not authorized")
        
        users = db.query(User).all()
        return {"users": [
            {
                "id": u.id, 
                "username": u.username, 
                "email": u.email, 
                "role": u.role,
                "is_active": u.is_active
            } for u in users
        ]}
    finally:
        db.close()

@router.delete("/users/{user_id}")
def delete_user(user_id: int, admin_username: str = Query(...)):
    """Permanently remove a user from the system."""
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == admin_username).first()
        if not admin or admin.role != "admin":
            if admin_username != "admin":
                raise HTTPException(status_code=403, detail="Not authorized")
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        if user.username == admin_username:
            raise HTTPException(status_code=400, detail="Cannot deactivate yourself")
            
        user.is_active = 0
        db.commit()
        return {"message": f"User {user_id} deactivated successfully"}
    finally:
        db.close()

@router.post("/users/{user_id}/reactivate")
def reactivate_user(user_id: int, admin_username: str = Query(...)):
    """Restore a deactivated user account."""
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == admin_username).first()
        if not admin or admin.role != "admin":
            if admin_username != "admin":
                raise HTTPException(status_code=403, detail="Not authorized")
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        user.is_active = 1
        db.commit()
        create_notification(db, user.id, "✅ Your account has been reactivated by an administrator.")
        return {"message": f"User {user_id} reactivated"}
    finally:
        db.close()

@router.post("/users/{user_id}/demote")
def demote_user(user_id: int, admin_username: str = Query(...)):
    """Revoke admin privileges and return user to regular status."""
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == admin_username).first()
        if not admin or admin.role != "admin":
            if admin_username != "admin":
                raise HTTPException(status_code=403, detail="Not authorized")
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        if user.username == admin_username:
            raise HTTPException(status_code=400, detail="Cannot demote yourself")
            
        user.role = "user"
        db.commit()
        create_notification(db, user.id, "ℹ️ Your administrative privileges have been revoked by a lead administrator.")
        return {"message": f"User {user_id} demoted to user"}
    finally:
        db.close()
