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


def test_register_success():
    response = client.post(
        "/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "Passw0rd!"
        }
    )
    assert response.status_code == 200
    assert "access_token" in response.json()

    # Verify login works
    login_resp = client.post(
        "/auth/login",
        json={"username": "testuser", "password": "Passw0rd!"}
    )
    assert login_resp.status_code == 200


def test_register_duplicate_username():
    response = client.post(
        "/auth/register",
        json={
            "username": "testuser",
            "email": "test2@example.com",
            "password": "Passw0rd!"
        }
    )
    assert response.status_code == 400
    assert "Username already exists" in response.json()["detail"]


def test_register_duplicate_email():
    response = client.post(
        "/auth/register",
        json={
            "username": "testuser2",
            "email": "test@example.com",
            "password": "Passw0rd!"
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
            "password": "weak"
        }
    )
    assert response.status_code == 400
    assert "Password must be 8+ chars" in response.json()["detail"]
