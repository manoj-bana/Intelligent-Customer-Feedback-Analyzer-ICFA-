from transformers import pipeline

print("Loading model... (downloads ~250MB on first run)")
sentiment = pipeline(
    "sentiment-analysis",
    model="distilbert-base-uncased-finetuned-sst-2-english"
)
print("Model loaded!\n")

test_reviews = [
    "This product is absolutely amazing, I love it!",
    "Terrible experience, worst service ever.",
    "It was okay, nothing special.",
    "The delivery was fast but the product quality was poor.",
    "Great value for money, highly recommend!",
]

print("=" * 50)
print("SENTIMENT ANALYSIS RESULTS")
print("=" * 50)
for review in test_reviews:
    result = sentiment(review[:512])[0]
    emoji = "✅" if result["label"] == "POSITIVE" else "❌"
    print(f"{emoji} {result['label']:10} (score: {result['score']:.3f})")
    print(f"   Review: {review}")
    print()
