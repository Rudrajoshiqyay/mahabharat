import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"), http_options={'timeout': 10.0})

models_to_test = ["gemini-2.5-flash", "gemini-3.7-flash", "gemini-flash-latest"]

for m in models_to_test:
    try:
        print(f"Testing {m}...")
        response = client.models.generate_content(model=m, contents="Reply with 'Hello'")
        print(f"Success! {m} says: {response.text}")
    except Exception as e:
        print(f"Failed {m}: {e}")
