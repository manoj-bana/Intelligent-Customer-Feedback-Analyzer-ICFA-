from fastapi.testclient import TestClient
from backend.main import app
import time

client = TestClient(app)

def test_full_workflow():

    login_response = client.post(
        "/auth/login",
        json={
            "username": "admin",
            "password": "admin123"
        }
    )

    assert login_response.status_code == 200

    token = login_response.json()["access_token"]

    csv_content = """feedback
Great service
Bad delivery
Customer support was helpful
"""

    response = client.post(
        "/feedback/analyze",
        files={"file": ("test.csv", csv_content, "text/csv")},
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    job_id = response.json()["job_id"]
    
    data = None
    for _ in range(10):
        res = client.get(f"/feedback/result/{job_id}").json()
        if res.get("status") == "completed":
            data = res["data"]
            break
        time.sleep(0.5)
    else:
        assert False, "Job did not complete in time"

    assert "results" in data
    assert "total" in data
