import pytest
from backend.database.models import User, Dataset, Organization, Notification, CompanyConfig, AdminRequest
from backend.auth import hash_password
from backend.database.db import SessionLocal
from unittest.mock import patch

@pytest.fixture
def admin_token(client):
    """Fixture to create an admin user and return their access token."""
    # 1. Register a user
    client.post("/auth/register", json={
        "username": "admin_test",
        "email": "admin_test@example.com",
        "password": "AdminPassword@123",
        "security_question": "Q",
        "security_answer": "A"
    })
    
    # 2. Manually elevate to admin in DB
    db = SessionLocal()
    user = db.query(User).filter(User.username == "admin_test").first()
    user.role = "admin"
    db.commit()
    db.close()
    
    # 3. Login to get token
    res = client.post("/auth/login", json={
        "username": "admin_test",
        "password": "AdminPassword@123"
    })
    return res.json()["access_token"]

@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}

@pytest.fixture
def user_token(client):
    """Fixture to create a regular user and return their access token."""
    client.post("/auth/register", json={
        "username": "regular_user",
        "email": "user@example.com",
        "password": "UserPassword@123",
        "security_question": "Q",
        "security_answer": "A"
    })
    res = client.post("/auth/login", json={
        "username": "regular_user",
        "password": "UserPassword@123"
    })
    return res.json()["access_token"]

@pytest.fixture
def user_headers(user_token):
    return {"Authorization": f"Bearer {user_token}"}

def test_get_all_users_as_admin(client, admin_headers):
    res = client.get("/admin/users", headers=admin_headers)
    assert res.status_code == 200
    assert "users" in res.json()
    # At least the admin user should be there
    assert len(res.json()["users"]) >= 1

def test_get_all_users_forbidden_for_regular_user(client, user_headers):
    res = client.get("/admin/users", headers=user_headers)
    assert res.status_code == 403

def test_get_system_stats(client, admin_headers):
    res = client.get("/admin/stats", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert "total_users" in data
    assert "total_datasets" in data
    assert "processing_jobs" in data

def test_update_user_role(client, admin_headers):
    # Create another regular user to update
    client.post("/auth/register", json={
        "username": "target_user",
        "email": "target@example.com",
        "password": "Password@123",
        "security_question": "Q",
        "security_answer": "A"
    })
    
    db = SessionLocal()
    target_user = db.query(User).filter(User.username == "target_user").first()
    user_id = target_user.id
    db.close()
    
    res = client.put(f"/admin/users/{user_id}/role?new_role=admin", headers=admin_headers)
    assert res.status_code == 200
    assert "Success" in res.json()["message"]
    
    # Verify in DB
    db = SessionLocal()
    updated_user = db.query(User).filter(User.id == user_id).first()
    assert updated_user.role == "admin"
    db.close()

def test_reset_user_password(client, admin_headers):
    # Register a user
    client.post("/auth/register", json={
        "username": "reset_test",
        "email": "reset@example.com",
        "password": "OldPassword@123",
        "security_question": "Q",
        "security_answer": "A"
    })
    
    db = SessionLocal()
    user = db.query(User).filter(User.username == "reset_test").first()
    user_id = user.id
    db.close()
    
    res = client.post(f"/admin/users/{user_id}/reset-password", headers=admin_headers)
    assert res.status_code == 200
    assert "new_password" in res.json()
    
    # Try to login with new password
    new_pwd = res.json()["new_password"]
    login_res = client.post("/auth/login", json={
        "username": "reset_test",
        "password": new_pwd
    })
    assert login_res.status_code == 200

def test_broadcast_notification(client, admin_headers):
    res = client.post("/admin/notifications/broadcast?message=Hello+System", headers=admin_headers)
    assert res.status_code == 200
    assert "Broadcast sent" in res.json()["message"]
    
    # Verify notifications created in DB
    db = SessionLocal()
    notifs = db.query(Notification).all()
    assert len(notifs) > 0
    db.close()

def test_organization_management(client, admin_headers):
    # 1. Create Organization
    org_data = {"name": "Test Org", "slug": "testorg"}
    res = client.post("/admin/organizations", json=org_data, headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["name"] == "Test Org"
    
    org_id = res.json()["id"]
    
    # 2. List Organizations
    list_res = client.get("/admin/organizations", headers=admin_headers)
    assert list_res.status_code == 200
    assert any(o["name"] == "Test Org" for o in list_res.json())
    
    # 3. Check Availability
    avail_res = client.get("/admin/check-availability?slug=testorg", headers=admin_headers)
    assert avail_res.json()["exists"] == True
    
    avail_res_2 = client.get("/admin/check-availability?slug=neworg", headers=admin_headers)
    assert avail_res_2.json()["exists"] == False
    
    # 4. Delete Organization
    del_res = client.delete(f"/admin/organizations/{org_id}", headers=admin_headers)
    assert del_res.status_code == 200
    
    # Verify deleted
    db = SessionLocal()
    org = db.query(Organization).filter(Organization.id == org_id).first()
    assert org is None
    db.close()

def test_config_management(client, admin_headers):
    # Update config
    config_update = {
        "pos_threshold": 0.1,
        "neg_threshold": -0.1,
        "pos_label": "Very Positive"
    }
    res = client.put("/admin/config/update", json=config_update, headers=admin_headers)
    assert res.status_code == 200
    
    # Get config
    get_res = client.get("/admin/config/get", headers=admin_headers)
    assert get_res.status_code == 200
    assert get_res.json()["pos_label"] == "Very Positive"

def test_delete_dataset(client, admin_headers):
    # Create dummy dataset record
    db = SessionLocal()
    # Need a user id
    user = db.query(User).first()
    ds = Dataset(
        case_id="TEST-CASE-123",
        user_id=user.id,
        filename="test.csv",
        file_path="nonexistent_test.csv"
    )
    db.add(ds)
    db.commit()
    db.close()
    
    res = client.delete("/admin/datasets/TEST-CASE-123", headers=admin_headers)
    assert res.status_code == 200
    
    # Verify deleted from DB
    db = SessionLocal()
    ds_check = db.query(Dataset).filter(Dataset.case_id == "TEST-CASE-123").first()
    assert ds_check is None
    db.close()

def test_admin_retry_dataset(client, admin_headers):
    # Setup dataset in failed state
    db = SessionLocal()
    user = db.query(User).first()
    ds = Dataset(
        case_id="RETRY-CASE",
        user_id=user.id,
        filename="fail.csv",
        file_path="fail.csv",
        review_status="failed",
        error_message="Manual failure"
    )
    db.add(ds)
    db.commit()
    db.close()
    
    # Mock process_data_pipeline to avoid actual processing/failure
    with patch("backend.routes.data_upload.process_data_pipeline") as mock_pipeline:
        # Retry
        res = client.post("/admin/datasets/RETRY-CASE/retry", headers=admin_headers)
        assert res.status_code == 200
    
    # Verify status changed
    db = SessionLocal()
    ds_check = db.query(Dataset).filter(Dataset.case_id == "RETRY-CASE").first()
    assert ds_check.review_status == "processing"
    assert ds_check.error_message is None
    db.close()

def test_clear_all_notifications(client, admin_headers):
    # Setup some notifications
    db = SessionLocal()
    user = db.query(User).first()
    db.add(Notification(user_id=user.id, message="Notif 1"))
    db.add(Notification(user_id=user.id, message="Notif 2"))
    db.commit()
    db.close()
    
    # Clear
    res = client.delete("/admin/notifications/clear-all", headers=admin_headers)
    assert res.status_code == 200
    
    # Verify DB empty
    db = SessionLocal()
    assert db.query(Notification).count() == 0
    db.close()

def test_non_admin_access(client, user_headers):
    # Test a few endpoints that should be restricted
    endpoints = [
        ("GET", "/admin/stats", None),
        ("GET", "/admin/datasets", None),
        ("POST", "/admin/notifications/broadcast?message=test", None),
        ("DELETE", "/admin/notifications/clear-all", None),
        ("POST", "/admin/organizations", {"name": "fail", "slug": "fail"}),
        ("GET", "/admin/organizations", None),
    ]
    
    for method, url, payload in endpoints:
        if method == "GET":
            res = client.get(url, headers=user_headers)
        elif method == "POST":
            res = client.post(url, json=payload, headers=user_headers)
        elif method == "DELETE":
            res = client.delete(url, headers=user_headers)
        elif method == "PUT":
            res = client.put(url, json=payload, headers=user_headers)
            
        assert res.status_code == 403, f"Endpoint {url} should be forbidden for regular user"

def test_admin_request_workflow(client):
    # 1. Register a user
    client.post("/auth/register", json={
        "username": "req_user",
        "email": "req@example.com",
        "password": "Password@123",
        "security_question": "Q",
        "security_answer": "A"
    })
    
    # 2. Request admin
    req_res = client.post("/auth/request-admin", json={
        "username": "req_user",
        "reason": "I need power"
    })
    assert req_res.status_code == 200
    
    # 3. Create a real admin to approve
    db = SessionLocal()
    admin_user = User(username="real_admin", email="ra@ex.com", password=hash_password("admin"), role="admin")
    db.add(admin_user)
    db.commit()
    
    request = db.query(AdminRequest).filter(AdminRequest.username == "req_user").first()
    req_id = request.id
    db.close()
    
    # 4. Fetch requests
    list_res = client.get(f"/auth/admin-requests?admin_username=real_admin")
    assert list_res.status_code == 200
    assert any(r["username"] == "req_user" for r in list_res.json()["requests"])
    
    # 5. Approve request
    app_res = client.post(f"/auth/admin-requests/{req_id}/approve?admin_username=real_admin")
    assert app_res.status_code == 200
    
    # 6. Verify role changed
    db = SessionLocal()
    user = db.query(User).filter(User.username == "req_user").first()
    assert user.role == "admin"
    db.close()

