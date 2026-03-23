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
        data = response.json()
        print("✅ API Response received!")
        print(f"  Total analyzed : {data['total']}")
        print(f"  Positive       : {data['positive']}")
        print(f"  Negative       : {data['negative']}")
        print(f"  Neutral        : {data['neutral']}")
        print(f"\n  Top keywords: {[k['word'] for k in data['keywords'][:5]]}")
        print(f"\n  Sample results:")
        for r in data["results"][:3]:
            print(f"    {r['label']:10} ({r['score']}) → {r['review'][:60]}")
    else:
        print(f"❌ Error {response.status_code}: {response.text}")

except requests.exceptions.ConnectionError:
    print("❌ Could not connect. Make sure backend is running!")
except FileNotFoundError:
    print("❌ sample_reviews.csv not found. Create it in ml/sample_data/")
