import os
import requests
from dotenv import load_dotenv

load_dotenv()
key = os.getenv("GEMINI_API_KEY")

prompt = "Hello"
payload = {"contents": [{"parts": [{"text": prompt}]}]}

for model in ["gemini-2.5-flash", "gemini-3.7-flash", "gemini-flash-latest"]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    res = requests.post(url, json=payload, timeout=10)
    print(f"{model}: {res.status_code}")
    if res.status_code == 200:
        print("Success:", res.json()["candidates"][0]["content"]["parts"][0]["text"].strip())
