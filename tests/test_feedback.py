from fastapi.testclient import TestClient
from backend.main import app
import time

client = TestClient(app)

def test_feedback_success():

    csv_content = """feedback
Great service
Bad delivery
Customer support was helpful
"""

    response = client.post(
        "/feedback/analyze",
        files={"file": ("test.csv", csv_content, "text/csv")}
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
        assert False, "Background task timed out"

    assert "total" in data
    assert "results" in data
    assert isinstance(data["results"], list)



def test_feedback_wrong_file():

    response = client.post(
        "/feedback/analyze",
        files={"file": ("test.txt", "invalid data", "text/plain")}
    )

    assert response.status_code == 400
    assert "Only CSV files allowed" in response.json()["detail"]



def test_feedback_no_text_column():

    csv_content = """id,value
1,100
2,200
"""

    response = client.post(
        "/feedback/analyze",
        files={"file": ("test.csv", csv_content, "text/csv")}
    )

    assert response.status_code == 200
    job_id = response.json()["job_id"]
    error_msg = ""
    for _ in range(10):
        res = client.get(f"/feedback/result/{job_id}").json()
        if res.get("status") == "failed":
            error_msg = res.get("error", "")
            break
        time.sleep(0.5)
    
    assert "No text column found" in error_msg