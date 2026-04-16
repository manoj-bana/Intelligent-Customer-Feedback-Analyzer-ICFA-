from fastapi import APIRouter, HTTPException, Query, Path, Depends, BackgroundTasks
from backend.auth import get_current_user, hash_password
from backend.database.models import User, Dataset, Notification, AdminRequest, Organization, CompanyConfig
from backend.database.db import SessionLocal
from pydantic import BaseModel
from typing import Optional
import os
import json
import datetime

router = APIRouter()

def verify_admin(current_user: User):
    """Ensure the requester is actually an admin."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden: Admin access required")
    return True

@router.get("/users")
def get_all_users(current_user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        verify_admin(current_user)
        users = db.query(User).all()
        return {
            "users": [
                {
                    "id": u.id,
                    "username": u.username,
                    "email": u.email,
                    "role": u.role,
                    "is_active": u.is_active,
                    "organization": u.organization.name if u.organization else "Unassigned"
                } for u in users
            ]
        }
    finally:
        db.close()

@router.get("/stats")
def get_system_stats(current_user: User = Depends(get_current_user)):
    """Fetch high-level system metrics (Admin only)."""
    db = SessionLocal()
    try:
        verify_admin(current_user)
        total_users = db.query(User).count()
        total_datasets = db.query(Dataset).count()
        failed_jobs = db.query(Dataset).filter(Dataset.review_status == "failed").count()
        processing_jobs = db.query(Dataset).filter(Dataset.review_status == "processing").count()
        
        # Jobs today
        today = datetime.datetime.utcnow().strftime('%Y-%m-%d')
        jobs_today = db.query(Dataset).filter(Dataset.created_at.like(f"{today}%")).count()
        
        return {
            "total_users": total_users,
            "total_datasets": total_datasets,
            "failed_jobs": failed_jobs,
            "processing_jobs": processing_jobs,
            "jobs_today": jobs_today
        }
    finally:
        db.close()

@router.get("/datasets")
def get_all_datasets(current_user: User = Depends(get_current_user)):
    """Fetch every dataset in the system with owner info (Admin only)."""
    db = SessionLocal()
    try:
        verify_admin(current_user)
        datasets = db.query(Dataset).order_by(Dataset.id.desc()).all()
        results = []
        for d in datasets:
            owner = db.query(User).filter(User.id == d.user_id).first()
            results.append({
                "case_id": d.case_id,
                "filename": d.filename,
                "task_type": d.task_type,
                "review_status": d.review_status,
                "created_date": d.created_at,
                "username": owner.username if owner else "Unknown",
                "error_message": d.error_message
            })
        return {"datasets": results}
    finally:
        db.close()


@router.put("/users/{user_id}/role")
def update_user_role(
    user_id: int = Path(...), 
    new_role: str = Query(...),
    current_user: User = Depends(get_current_user)
):
    db = SessionLocal()
    try:
        verify_admin(current_user)
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
    current_user: User = Depends(get_current_user)
):
    db = SessionLocal()
    try:
        verify_admin(current_user)
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Generate a secure random temporary password
        import secrets
        import string
        alphabet = string.ascii_letters + string.digits
        base = ''.join(secrets.choice(alphabet) for _ in range(9))
        new_password = (
            secrets.choice(string.ascii_uppercase)
            + base
            + secrets.choice(string.digits)
            + secrets.choice("@$!%*?&")
        )
        
        user.password = hash_password(new_password)
        db.commit()
        return {"message": "Password has been reset", "new_password": new_password}
    finally:
        db.close()


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int = Path(...),
    current_user: User = Depends(get_current_user)
):
    db = SessionLocal()
    try:
        verify_admin(current_user)
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Hard delete associated datasets
        datasets = db.query(Dataset).filter(Dataset.user_id == user.id).all()
        for dataset in datasets:
            try:
                if os.path.exists(dataset.file_path): os.remove(dataset.file_path)
            except: pass
            db.delete(dataset)

        db.delete(user)
        db.commit()
        return {"message": "User and all data deleted"}
    finally:
        db.close()


@router.post("/datasets/{case_id}/retry")
def admin_retry_dataset(
    case_id: str, 
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """Reset status to 'processing' and re-trigger background task (Admin only)."""
    from backend.routes.data_upload import process_data_pipeline
    db = SessionLocal()
    try:
        verify_admin(current_user)
        dataset = db.query(Dataset).filter(Dataset.case_id == case_id).first()
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")
            
        dataset.review_status = "processing"
        dataset.error_message = None
        db.commit()
        
        background_tasks.add_task(process_data_pipeline, dataset.case_id, dataset.file_path, dataset.task_type)
        return {"message": f"Retrying dataset {case_id}"}
    finally:
        db.close()


@router.delete("/datasets/{case_id}")
def admin_delete_dataset(case_id: str, current_user: User = Depends(get_current_user)):
    """Hard delete any dataset by ID (Admin only)."""
    db = SessionLocal()
    try:
        verify_admin(current_user)
        ds = db.query(Dataset).filter(Dataset.case_id == case_id).first()
        if not ds:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        try:
            if os.path.exists(ds.file_path): os.remove(ds.file_path)
        except: pass
        
        db.delete(ds)
        db.commit()
        return {"message": f"Dataset {case_id} deleted"}
    finally:
        db.close()


@router.post("/notifications/broadcast")
def broadcast_notification(message: str = Query(...), current_user: User = Depends(get_current_user)):
    """Send a notification to ALL users."""
    db = SessionLocal()
    try:
        verify_admin(current_user)
        users = db.query(User).all()
        for u in users:
            notif = Notification(user_id=u.id, message=f"📢 {message}", is_read=0)
            db.add(notif)
        db.commit()
        return {"message": f"Broadcast sent to {len(users)} users"}
    finally:
        db.close()


@router.delete("/notifications/clear-all")
def clear_all_notifications(current_user: User = Depends(get_current_user)):
    """Bulk clear all notifications (Admin only)."""
    db = SessionLocal()
    try:
        verify_admin(current_user)
        db.query(Notification).delete()
        db.commit()
        return {"message": "All notifications cleared"}
    finally:
        db.close()

# --- Multi-Tenant Configuration Endpoints ---

# --- Unified Admin Configuration APIs ---

class UnifiedConfigUpdate(BaseModel):
    org_id: Optional[int] = None 
    pos_threshold: Optional[float] = None
    neg_threshold: Optional[float] = None
    pos_label: Optional[str] = None
    neg_label: Optional[str] = None
    neu_label: Optional[str] = None
    keyword_boosters: Optional[str] = None
    
    # Churn
    high_risk_threshold: Optional[float] = None
    medium_risk_threshold: Optional[float] = None
    low_risk_threshold: Optional[float] = None
    churn_rules: Optional[dict] = None
    
    # Mapping 
    column_mapper: Optional[dict] = None

@router.get("/config/get")
@router.get("/get-config") 
def get_unified_config(org_id: Optional[int] = Query(None), current_user: User = Depends(get_current_user)):
    """Fetch complete config JSON for a specific organization or global default."""
    db = SessionLocal()
    try:
        # If admin provides org_id, use it. Else use their own.
        target_org_id = org_id if current_user.role == "admin" else current_user.org_id
        
        config = db.query(CompanyConfig).filter(CompanyConfig.org_id == target_org_id).first()
        if not config:
            return {
                "pos_threshold": 0.05, "neg_threshold": -0.05,
                "high_risk_threshold": 0.70, "medium_risk_threshold": 0.40,
                "low_risk_threshold": 0.10,
                "org_id": target_org_id
            }
        return config
    finally:
        db.close()

@router.put("/config/update")
@router.put("/update-config") 
def update_unified_config(data: UnifiedConfigUpdate, current_user: User = Depends(get_current_user)):
    verify_admin(current_user)
    db = SessionLocal()
    try:
        target_org_id = data.org_id
        
        config = db.query(CompanyConfig).filter(CompanyConfig.org_id == target_org_id).first()
        if not config:
            config = CompanyConfig(org_id=target_org_id)
            db.add(config)
        
        update_data = data.dict(exclude_unset=True)
        if "org_id" in update_data: del update_data["org_id"]
        
        for field, value in update_data.items():
            setattr(config, field, value)
            
        db.commit()
        return {"message": "Configuration saved successfully"}
    finally:
        db.close()

# --- Organization Management ---

class OrgCreate(BaseModel):
    name: str
    slug: str

@router.post("/organizations")
def create_organization(data: OrgCreate, current_user: User = Depends(get_current_user)):
    """Create a new organization (Admin only)."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    db = SessionLocal()
    try:
        # Check for existing name or slug
        existing_name = db.query(Organization).filter(Organization.name == data.name).first()
        if existing_name:
            raise HTTPException(status_code=400, detail=f"Company name '{data.name}' already exists.")
            
        existing_slug = db.query(Organization).filter(Organization.slug == data.slug.lower().strip()).first()
        if existing_slug:
            raise HTTPException(status_code=400, detail=f"Company code (slug) '{data.slug}' is already taken.")

        new_org = Organization(name=data.name, slug=data.slug.lower().strip())
        db.add(new_org)
        db.commit()
        db.refresh(new_org)
        return new_org
    finally:
        db.close()

@router.get("/organizations")
def list_organizations(current_user: User = Depends(get_current_user)):
    """List all organizations (Admin only)."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    db = SessionLocal()
    try:
        return db.query(Organization).all()
    finally:
        db.close()

@router.get("/check-availability")
def check_org_availability(name: str = None, slug: str = None, current_user: User = Depends(get_current_user)):
    """Check if an organization name or slug is available."""
    if current_user.role != "admin":
         raise HTTPException(status_code=403, detail="Admin access required")
    db = SessionLocal()
    try:
        if name:
            exists = db.query(Organization).filter(Organization.name.ilike(name.strip())).first() is not None
            return {"exists": exists}
        if slug:
            exists = db.query(Organization).filter(Organization.slug == slug.lower().strip()).first() is not None
            return {"exists": exists}
        return {"exists": False}
    finally:
        db.close()
