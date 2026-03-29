from fastapi.testclient import TestClient
from backend.main import app
import time

client = TestClient(app)

def test_churn_success():

    csv_content = """tenure,MonthlyCharges,TotalCharges,Contract,PaymentMethod,InternetService
12,70,840,Month-to-month,Electronic check,Fiber optic
24,60,1440,One year,Credit card (automatic),DSL
36,80,2880,Two year,Mailed check,No
"""

    response = client.post(
        "/churn/predict",
        files={"file": ("test.csv", csv_content, "text/csv")}
    )

    assert response.status_code == 200

    job_id = response.json()["job_id"]
    data = None
    last_res = {}
    for _ in range(20):
        res = client.get(f"/churn/result/{job_id}").json()
        last_res = res
        if res.get("status") == "completed":
            data = res["data"]
            break
        if res.get("status") == "failed":
            assert False, f"Job failed: {res.get('error')}"
        time.sleep(0.5)
    else:
        assert False, f"Background task timed out. Last status: {last_res}"

    assert "total_customers" in data
    assert "churn_rate" in data


def test_churn_wrong_file():

    response = client.post(
        "/churn/predict",
        files={"file": ("test.txt", "invalid", "text/plain")}
    )

    assert response.status_code == 400
    assert "Only CSV files allowed" in response.json()["detail"]


def test_churn_missing_columns():

    csv_content = """id,value
1,10
2,20
"""

    response = client.post(
        "/churn/predict",
        files={"file": ("test.csv", csv_content, "text/csv")}
    )

    assert response.status_code == 200

    job_id = response.json()["job_id"]
    error_msg = ""
    for _ in range(10):
        res = client.get(f"/churn/result/{job_id}").json()
        if res.get("status") == "failed":
            error_msg = res.get("error", "")
            break
        time.sleep(0.5)

    assert len(error_msg) > 0