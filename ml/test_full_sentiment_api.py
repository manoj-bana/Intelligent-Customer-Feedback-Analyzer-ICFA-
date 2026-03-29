"""
Day 3 - Person 3
Test the complete end-to-end API flow for sentiment analysis.
Make sure the backend is running first:
  uvicorn backend.main:app --reload

Run: python ml/test_full_sentiment_api.py
"""

import requests

API_URL = "http://127.0.0.1:8000"

print("Testing full sentiment API flow...")
print("Make sure backend is running: uvicorn backend.main:app --reload\n")

try:
    with open("ml/sample_data/sample_reviews.csv", "rb") as f:
        response = requests.post(
            f"{API_URL}/feedback/analyze",
            files={"file": ("sample_reviews.csv", f, "text/csv")},
            timeout=120
        )

    if response.status_code == 200:
        job_id = response.json()["job_id"]
        print(f"✅ Job accepted! ID: {job_id}")
        
        import time
        data = None
        for _ in range(60):
            res = requests.get(f"{API_URL}/feedback/result/{job_id}", timeout=60).json()
            if res.get("status") == "completed":
                data = res["data"]
                break
            elif res.get("status") == "failed":
                print(f"❌ Processing failed: {res.get('error')}")
                exit(1)
            time.sleep(1)
            
        if not data:
            print("❌ Job timed out.")
            exit(1)

        print("✅ API Response data extracted!")
        print(f"  Total analyzed : {data.get('total', 0)}")
        print(f"  Positive       : {data.get('positive', 0)}")
        print(f"  Negative       : {data.get('negative', 0)}")
        print(f"  Neutral        : {data.get('neutral', 0)}")
        print(f"\n  Top keywords: {[k['word'] for k in data.get('keywords', [])[:5]]}")
        print(f"\n  Sample results:")
        for r in data.get("results", [])[:3]:
            print(f"    {r.get('label', 'N/A'):10} ({r.get('score', 0)}) → {r.get('review', '')[:60]}")
    else:
        print(f"❌ Error {response.status_code}: {response.text}")

except requests.exceptions.ConnectionError:
    print("❌ Could not connect. Make sure backend is running!")
except FileNotFoundError:
    print("❌ sample_reviews.csv not found. Create it in ml/sample_data/")
