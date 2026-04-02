import nltk
import ssl
import urllib.request

try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

# Add a User-Agent header
opener = urllib.request.build_opener()
opener.addheaders = [('User-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')]
urllib.request.install_opener(opener)

print("Attempting to download stopwords...")
try:
    nltk.download("stopwords", raise_on_error=True)
    nltk.download("vader_lexicon", raise_on_error=True)
    print("Success downloading NLTK datasets!")
except Exception as e:
    print(f"Failed to download: {e}")
