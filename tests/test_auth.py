"""
Tests for authentication: login, register, forgot/reset password.
"""


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

import uuid

<<<<<<< HEAD
def test_register_success():
    unique_id = str(uuid.uuid4())[:8]
    username = f"user_{unique_id}"
    email = f"test_{unique_id}@example.com"
    
    response = client.post(
        "/auth/register",
        json={
            "username": username,
            "email": email,
            "password": "Passw0rd!",
            "security_question": "q1",
            "security_answer": "a1"
        }
    )
    assert response.status_code == 200
    assert "access_token" in response.json()

    # Verify login works
    login_resp = client.post(
        "/auth/login",
        json={"username": username, "password": "Passw0rd!"}
    )
    assert login_resp.status_code == 200


def test_register_duplicate_username():
    unique_id = str(uuid.uuid4())[:8]
    username = f"dup_{unique_id}"
    email1 = f"e1_{unique_id}@example.com"
    email2 = f"e2_{unique_id}@example.com"
    
    # First registration
    client.post(
        "/auth/register",
        json={
            "username": username,
            "email": email1,
            "password": "Passw0rd!",
            "security_question": "q1",
            "security_answer": "a1"
        }
    )
    
    # Second registration with same username
    response = client.post(
        "/auth/register",
        json={
            "username": username,
            "email": email2,
            "password": "Passw0rd!",
            "security_question": "q1",
            "security_answer": "a1"
        }
    )
    assert response.status_code == 400
    assert "Username already exists" in response.json()["detail"]


def test_register_duplicate_email():
    unique_id = str(uuid.uuid4())[:8]
    user1 = f"u1_{unique_id}"
    user2 = f"u2_{unique_id}"
    email = f"dup_{unique_id}@example.com"
    
    # First registration
    client.post(
        "/auth/register",
        json={
            "username": user1,
            "email": email,
            "password": "Passw0rd!",
            "security_question": "q1",
            "security_answer": "a1"
        }
    )
    
    # Second registration with same email
    response = client.post(
        "/auth/register",
        json={
            "username": user2,
            "email": email,
            "password": "Passw0rd!",
            "security_question": "q1",
            "security_answer": "a1"
        }
    )
    assert response.status_code == 400
    assert "Email already registered" in response.json()["detail"]


def test_register_weak_password():
    response = client.post(
        "/auth/register",
        json={
            "username": "weakuser",
            "email": "weak@example.com",
            "password": "weak",
            "security_question": "q1",
            "security_answer": "a1"
        }
    )
    assert response.status_code == 400
    assert "Password must be 8+ chars" in response.json()["detail"]
=======
def test_root(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "ICFA" in res.json()["message"]


# ─── LOGIN ───

def test_login_default_admin(client):
    res = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    assert res.status_code == 200
    assert "access_token" in res.json()
    assert res.json()["username"] == "admin"


def test_login_wrong_password(client):
    res = client.post("/auth/login", json={"username": "admin", "password": "wrong"})
    assert res.status_code == 401


def test_login_nonexistent_user(client):
    res = client.post("/auth/login", json={"username": "ghost", "password": "x"})
    assert res.status_code == 401


# ─── REGISTER ───

def test_register_success(client):
    res = client.post("/auth/register", json={
        "username": "newuser",
        "email": "new@example.com",
        "password": "Strong@123",
        "security_question": "Pet?",
        "security_answer": "cat"
    })
    assert res.status_code == 200
    assert "access_token" in res.json()


def test_register_duplicate_username(client, registered_user):
    res = client.post("/auth/register", json={
        "username": registered_user["username"],
        "email": "other@example.com",
        "password": "Strong@123",
        "security_question": "Q?",
        "security_answer": "A"
    })
    assert res.status_code == 400
    assert "already exists" in res.json()["detail"]


def test_register_weak_password(client):
    res = client.post("/auth/register", json={
        "username": "weakuser",
        "email": "weak@example.com",
        "password": "short",
        "security_question": "Q?",
        "security_answer": "A"
    })
    assert res.status_code == 400


def test_register_bad_email(client):
    res = client.post("/auth/register", json={
        "username": "bademail",
        "email": "not-an-email",
        "password": "Strong@123",
        "security_question": "Q?",
        "security_answer": "A"
    })
    assert res.status_code == 400


# ─── FORGOT / RESET PASSWORD ───

def test_forgot_password(client, registered_user):
    res = client.post("/auth/forgot-password", json={"username": registered_user["username"]})
    assert res.status_code == 200
    assert "security_question" in res.json()


def test_forgot_password_nonexistent(client):
    res = client.post("/auth/forgot-password", json={"username": "nobody"})
    assert res.status_code == 404


def test_verify_security_answer(client, registered_user):
    res = client.post("/auth/verify-security-answer", json={
        "username": registered_user["username"],
        "answer": registered_user["security_answer"]
    })
    assert res.status_code == 200
    assert "temp_token" in res.json()


def test_verify_wrong_answer(client, registered_user):
    res = client.post("/auth/verify-security-answer", json={
        "username": registered_user["username"],
        "answer": "wronganswer"
    })
    assert res.status_code == 401


def test_login_after_register(client, registered_user):
    res = client.post("/auth/login", json={
        "username": registered_user["username"],
        "password": registered_user["password"]
    })
    assert res.status_code == 200
    assert res.json()["username"] == registered_user["username"]
>>>>>>> bd5c89ca96a5b8bb623b80c2b284d392f6a492ae
