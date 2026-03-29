>>>>>>> bd5c89ca96a5b8bb623b80c2b284d392f6a492ae
"""
Integration tests for the ingestion pipeline API: upload, list, results, retry, delete.
"""
import os
import io


<<<<<<< HEAD
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
=======
# ─── UPLOAD ───
>>>>>>> bd5c89ca96a5b8bb623b80c2b284d392f6a492ae
=======
"""
Integration tests for the ingestion pipeline API: upload, list, results, retry, delete.
"""
import os
import io


# ─── UPLOAD ───
=======
>>>>>>> bd5c89ca96a5b8bb623b80c2b284d392f6a492ae
"""
Integration tests for the ingestion pipeline API: upload, list, results, retry, delete.
"""
import os
import io


<<<<<<< HEAD
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
=======
# ─── UPLOAD ───
>>>>>>> bd5c89ca96a5b8bb623b80c2b284d392f6a492ae

def test_upload_sentiment_csv(client, registered_user):
    csv_content = "review,rating\nGreat product!,5\nTerrible quality.,1\n"
    files = {"file": ("test.csv", io.BytesIO(csv_content.encode()), "text/csv")}
    data = {"username": registered_user["username"], "task_type": "Sentiment Analysis"}

    res = client.post("/ingest/upload", files=files, data=data)
    assert res.status_code == 200
    assert "case_id" in res.json()
    assert res.json()["filename"] == "test.csv"


def test_upload_missing_user(client):
    csv_content = "review\nHello\n"
    files = {"file": ("test.csv", io.BytesIO(csv_content.encode()), "text/csv")}
    data = {"username": "nonexistent_user", "task_type": "Sentiment Analysis"}

    res = client.post("/ingest/upload", files=files, data=data)
    assert res.status_code in [404, 500]


# ─── LIST CASES ───

def test_list_cases_empty(client, registered_user):
    res = client.get(f"/ingest/cases/{registered_user['username']}")
    assert res.status_code == 200
    assert res.json()["cases"] == []


def test_list_cases_after_upload(client, registered_user):
    csv_content = "review\nGreat!\n"
    files = {"file": ("test.csv", io.BytesIO(csv_content.encode()), "text/csv")}
    data = {"username": registered_user["username"], "task_type": "Sentiment Analysis"}
    client.post("/ingest/upload", files=files, data=data)

    res = client.get(f"/ingest/cases/{registered_user['username']}")
    assert res.status_code == 200
    cases = res.json()["cases"]
    assert len(cases) == 1
    assert cases[0]["filename"] == "test.csv"
    assert cases[0]["task_type"] == "Sentiment Analysis"


def test_list_cases_nonexistent_user(client):
    res = client.get("/ingest/cases/nobody")
    assert res.status_code == 404


# ─── DELETE CASE ───

def test_delete_case(client, registered_user):
    csv_content = "review\nDelete me\n"
    files = {"file": ("delete.csv", io.BytesIO(csv_content.encode()), "text/csv")}
    data = {"username": registered_user["username"], "task_type": "Sentiment Analysis"}
    upload_res = client.post("/ingest/upload", files=files, data=data)
    case_id = upload_res.json()["case_id"]

    del_res = client.delete(f"/ingest/cases/{case_id}")
    assert del_res.status_code == 200

    # Verify it's gone
    list_res = client.get(f"/ingest/cases/{registered_user['username']}")
    assert len(list_res.json()["cases"]) == 0


def test_delete_nonexistent_case(client):
    res = client.delete("/ingest/cases/FAKE_ID")
    assert res.status_code == 404


# ─── RETRY CASE ───

def test_retry_case(client, registered_user):
    csv_content = "review\nRetry me\n"
    files = {"file": ("retry.csv", io.BytesIO(csv_content.encode()), "text/csv")}
    data = {"username": registered_user["username"], "task_type": "Sentiment Analysis"}
    upload_res = client.post("/ingest/upload", files=files, data=data)
    case_id = upload_res.json()["case_id"]

    retry_res = client.post(f"/ingest/cases/{case_id}/retry")
    assert retry_res.status_code == 200
    assert "queued" in retry_res.json()["message"].lower()


def test_retry_nonexistent_case(client):
    res = client.post("/ingest/cases/FAKE_ID/retry")
    assert res.status_code == 404


# ─── RESULTS ───

def test_results_not_found(client):
    res = client.get("/ingest/results/FAKE_ID")
    assert res.status_code == 404
