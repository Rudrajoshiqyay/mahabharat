import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv(dotenv_path="../.env")
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

try:
    completion = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {"role": "system", "content": "You are a JSON-only extraction bot. Output only valid JSON without markdown tags."},
            {"role": "user", "content": 'Extract {"name": "Bob"} from "My name is Bob"'}
        ],
        temperature=0.2,
        max_tokens=500
    )
    print("OUTPUT:", completion.choices[0].message.content)
except Exception as e:
    print("ERROR:", e)
