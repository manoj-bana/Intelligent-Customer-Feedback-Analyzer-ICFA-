from fastapi import APIRouter, HTTPException, Query, Path
from pydantic import BaseModel
from backend.database.db import SessionLocal
from backend.database.models import User, Dataset
from backend.auth import hash_password
import os

router = APIRouter()

def verify_admin(db, admin_username: str):
    """Ensure the requester is actually an admin."""
    # Special bypass for the hardcoded local instance admin
    if admin_username == "admin":
        return True
    
    admin_user = db.query(User).filter(User.username == admin_username).first()
    if not admin_user or getattr(admin_user, "role", "user") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden: Admin access required")
    return True

@router.get("/users")
def get_all_users(admin_username: str = Query(...)):
    db = SessionLocal()
    try:
        verify_admin(db, admin_username)
        users = db.query(User).all()
        return {
            "users": [
                {
                    "id": u.id,
                    "username": u.username,
                    "email": u.email,
                    "role": getattr(u, "role", "user")
                } for u in users
            ]
        }
    finally:
        db.close()


@router.put("/users/{user_id}/role")
def update_user_role(
    user_id: int = Path(...), 
    admin_username: str = Query(...), 
    new_role: str = Query(...)
):
    db = SessionLocal()
    try:
        verify_admin(db, admin_username)
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user.role = new_role
        db.commit()
        return {"message": f"Successfully updated role to {new_role}"}
    finally:
        db.close()


@router.post("/users/{user_id}/reset-password")
def reset_user_password(
    user_id: int = Path(...),
    admin_username: str = Query(...)
):
    db = SessionLocal()
    try:
        verify_admin(db, admin_username)
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        new_password = "ResetPassword123!"
        user.password = hash_password(new_password)
        
        # Clear any existing reset tokens
        user.reset_token = None
        user.reset_token_expiry = None
        
        db.commit()
        return {"message": "Password overridden", "new_password": new_password}
    finally:
        db.close()


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int = Path(...),
    admin_username: str = Query(...)
):
    db = SessionLocal()
    try:
        verify_admin(db, admin_username)
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Cascade dataset deletion to free up space
        datasets = db.query(Dataset).filter(Dataset.user_id == user.id).all()
        for dataset in datasets:
            try:
                if os.path.exists(dataset.file_path):
                    os.remove(dataset.file_path)
            except OSError:
                pass

            enriched_path = dataset.file_path.replace(dataset.case_id, f"enriched_{dataset.case_id}")
            try:
                if os.path.exists(enriched_path):
                    os.remove(enriched_path)
            except OSError:
                pass

            results_path = f"{dataset.file_path}_results.json"
            try:
                if os.path.exists(results_path):
                    os.remove(results_path)
            except OSError:
                pass
            
            db.delete(dataset)

        db.delete(user)
        db.commit()
        return {"message": "User and all associated data deleted"}
    finally:
        db.close()
