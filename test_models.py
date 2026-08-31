import os
from dotenv import load_dotenv
import requests

load_dotenv()
key = os.getenv("GEMINI_API_KEY")
res = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={key}")
models = res.json().get('models', [])
for m in models:
    if "flash" in m['name']:
        print(m['name'])
