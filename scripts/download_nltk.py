import nltk
import ssl
import time

def setup_nltk():
    print("📥 Starting NLTK Resource Downloader...")
    
    # Fix for some SSL certificate issues on Windows/macOS
    try:
        _create_unverified_https_context = ssl._create_unverified_context
    except AttributeError:
        pass
    else:
        ssl._create_default_https_context = _create_unverified_https_context

    resources = ['stopwords', 'wordnet', 'omw-1.4', 'punkt']
    
    for res in resources:
        print(f"📦 Downloading '{res}'...")
        try:
            nltk.download(res, halt_on_error=False)
            print(f"✅ Successfully downloaded '{res}'")
        except Exception as e:
            print(f"❌ Failed to download '{res}': {e}")
            print("   (Don't worry, the system will use the built-in fallback stopwords)")
        time.sleep(1)

    print("\n✨ Setup complete! You can now run the training script.")

if __name__ == "__main__":
    setup_nltk()
