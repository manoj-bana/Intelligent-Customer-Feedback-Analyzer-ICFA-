from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_login_success():

    response = client.post(
        "/auth/login",
        json={"username": "admin", "password": "admin123"}
    )

    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_fail():
    response = client.post(
        "/auth/login",
        json={"username": "admin", "password": "wrong"}
    )
    assert response.status_code == 401

import uuid

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
