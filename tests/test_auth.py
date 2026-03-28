"""
Tests for authentication: login, register, forgot/reset password.
"""


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


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
