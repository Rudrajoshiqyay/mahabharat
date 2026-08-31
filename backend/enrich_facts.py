import os
import json
import requests
from dotenv import load_dotenv
from google import genai
from google.genai import types
from neo4j import GraphDatabase

load_dotenv(dotenv_path="../.env")
gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
db_driver = GraphDatabase.driver(os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD")))

def search_wikipedia(query):
    # Add 'Mahabharata' to the search to ensure we hit the right entity
    url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={query} Mahabharata&utf8=&format=json"
    headers = {"User-Agent": "MahabharataGraphCrawler/1.0 (rudrajoshi@example.com)"}
    try:
        res = requests.get(url, headers=headers).json()
        search_results = res.get("query", {}).get("search", [])
        if search_results:
            title = search_results[0]["title"]
            summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title.replace(' ', '_')}"
            sum_res = requests.get(summary_url, headers=headers).json()
            return sum_res.get("extract", "")
    except Exception as e:
        print(f"Wiki API Error: {e}")
    return ""

def extract_fact_from_wiki(text, name):
    if not text: return None
    
    prompt = f'''Read this Wikipedia summary about {name}:
{text}

Extract one highly interesting fact, folklore, or legend about this entity.
Classify its type as one of: "Fact", "Folklore", "Legend", "Retelling".
(e.g., if it says people believe something but it's not confirmed, classify as Legend. If it's from a specific retelling/purana, say Retelling.)
Required STRICT JSON Schema:
{{
    "fact": "The interesting fact...",
    "type": "Legend"
}}'''
    
    try:
        response = gemini_client.models.generate_content(
            model='gemini-3.6-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.3
            )
        )
        return json.loads(response.text.strip())
    except Exception as e:
        print(f"Gemini Error: {e}")
        return None

def main():
    print("Enriching Section 1 Part 1 Characters with Wikipedia Facts...")
    with db_driver.session() as session:
        result = session.run("""
            MATCH (s:Section {global_id: '1_1'})-[r:MENTIONS_CHARACTER]->(c:Character)
            RETURN c.name AS name
        """)
        char_names = [record["name"] for record in result]
        
        for name in char_names:
            clean_name = name.split("(")[-1].replace(")", "") if "(" in name else name
            print(f"Looking up {clean_name} on Wikipedia...")
            
            summary = search_wikipedia(clean_name)
            
            if summary:
                fact_data = extract_fact_from_wiki(summary, clean_name)
                if fact_data and fact_data.get("fact"):
                    print(f"  -> Extracted {fact_data['type']}: {fact_data['fact']}")
                    session.run("""
                        MATCH (c:Character {name: $name})
                        MERGE (f:Fact {content: $fact})
                        SET f.type = $type, f.source = 'Wikipedia'
                        MERGE (c)-[:HAS_FACT]->(f)
                    """, name=name, fact=fact_data["fact"], type=fact_data["type"])
            else:
                print(f"  No Wikipedia page found.")

if __name__ == "__main__":
    main()
