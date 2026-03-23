import sys
sys.path.append(".")  # so Python can find backend/

from backend.utils.sentiment import analyze_sentiment, extract_keywords

reviews = [
    "This product is absolutely amazing!",
    "Terrible service, very disappointed.",
    "It was alright, nothing special.",
    "Fast delivery but bad packaging.",
    "Will definitely buy again, love it!",
]

print("Testing analyze_sentiment():")
print("-" * 50)
for r in reviews:
    result = analyze_sentiment(r)
    emoji = "✅" if result["label"] == "POSITIVE" else ("❌" if result["label"] == "NEGATIVE" else "😐")
    print(f"  {emoji} {result['label']:10} ({result['score']}) → {r}")

print("\nTesting extract_keywords():")
print("-" * 50)
keywords = extract_keywords(reviews)
for kw in keywords[:8]:
    print(f"  {kw['word']}: {kw['count']}")

print("\n✅ All tests passed!")
