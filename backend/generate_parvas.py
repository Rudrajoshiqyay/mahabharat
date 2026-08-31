import os
import json
import time
from groq import Groq
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv(dotenv_path="../.env")
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

URI = os.getenv("NEO4J_URI")
USER = os.getenv("NEO4J_USERNAME")
PWD = os.getenv("NEO4J_PASSWORD")
db_driver = GraphDatabase.driver(URI, auth=(USER, PWD))

parvas = [
    "Anukramanika Parva", "Sangraha Parva", "Paushya Parva", "Pauloma Parva", "Astika Parva", 
    "Adivansavatarana Parva", "Sambhava Parva", "Jatugriha Parva", "Hidimva-vadha Parva", 
    "Vaka-vadha Parva", "Chaitraratha Parva", "Swayamvara Parva", "Vaivahika Parva", 
    "Viduragamana Parva", "Rajya-labha Parva", "Arjuna-vanavasa Parva", "Subhadra-harana Parva", 
    "Haranaharana Parva", "Khandava-daha Parva"
]

def generate_and_push():
    for parva in parvas:
        print(f"Generating summary for {parva}...", flush=True)
        prompt = f"""You are an expert historian of the Mahabharata. Write an 'Executive Summary' specifically for the '{parva}' (a sub-parva of Book 1: Adi Parva).
        
        CRITICAL GOAL:
        The reader wants to use this summary to SKIP reading the individual sections of this Parva. You MUST tell them exactly what stories, events, and plot points happen inside this specific Parva so they don't miss anything important. Do NOT use placeholder text like '...'. You must write the actual story.
        
        Output STRICT JSON with exactly these two keys:
        {{
            "events_summary": "A highly detailed 2-3 paragraph summary of the actual plot events, stories, and character actions that occur strictly within this specific Parva. Do not summarize the whole epic.",
            "next_context": "1-2 sentences explaining how the events of this Parva set the stage or transition into the next Parva."
        }}
        """
        
        for attempt in range(3):
            try:
                completion = groq_client.chat.completions.create(
                    model="allam-2-7b",
                    messages=[
                        {"role": "system", "content": "You are a JSON-only bot. You output highly accurate, strictly scoped summaries."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2,
                    max_tokens=1500
                )
                
                text_out = completion.choices[0].message.content.strip()
                
                start_idx = text_out.find("{")
                end_idx = text_out.rfind("}")
                if start_idx != -1 and end_idx != -1:
                    data = json.loads(text_out[start_idx:end_idx+1], strict=False)
                    
                    events = data.get("events_summary", "")
                    next_ctx = data.get("next_context", "")
                    
                    final_summary = f"WHAT HAPPENS IN THIS PARVA:\n{events}\n\nCONTEXT FOR THE NEXT PARVA:\n{next_ctx}"
                    
                    with db_driver.session() as session:
                        session.run("MATCH (p:Parva {title: $title}) SET p.summary = $summary", title=parva, summary=final_summary)
                        
                    print(f"  [OK] Saved executive summary for {parva}", flush=True)
                    break
            except Exception as e:
                print(f"  [Error] {e}", flush=True)
                time.sleep(2)
        
        time.sleep(10)

generate_and_push()
db_driver.close()
