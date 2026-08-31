import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv(dotenv_path="../.env")
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

for m in client.models.list().data:
    print(m.id)
