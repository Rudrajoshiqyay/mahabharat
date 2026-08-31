import os
import json
import sys
from dotenv import load_dotenv
from google import genai
from google.genai import types
from neo4j import GraphDatabase
from sanskrit_scraper import get_sanskrit_verses

# Ensure utf-8 stdout for Windows
sys.stdout.reconfigure(encoding='utf-8')

load_dotenv(dotenv_path="../.env")
gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
db_driver = GraphDatabase.driver(os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD")))

def main():
    print("Fetching Sanskrit verses for Part 2...")
    verses = get_sanskrit_verses(1, 2)
    if not verses:
        print("Failed to get verses.")
        return
        
    short_verses = "\\n".join(verses.split("\\n")[:4])
    print("Verses fetched successfully.")

    prompt = f"""You are an expert in Sanskrit literature and the Mahabharata.
    I have scraped the following Sanskrit verses for Section 1.2 of the Mahabharata:
    {short_verses}
    
    Provide a highly interesting, mind-blowing fact about these specific Sanskrit verses.
    Explain the profound philosophical, linguistic, or cultural significance of these words.
    Output STRICT JSON: 
    {{ 
        "fact": "The interesting fact...", 
        "sanskrit_verse": "The original sanskrit verse provided above", 
        "translation": "The English translation of the verse" 
    }}"""
    
    print("Generating insight using Gemini...")
    response = gemini_client.models.generate_content(
        model='gemini-3.6-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.3
        )
    )
    data = json.loads(response.text.strip())
    
    print("Pushing to Neo4j...")
    with db_driver.session() as session:
        session.run("""
            MATCH (s:Section {global_id: '1_2'})
            MERGE (i:Insight {type: 'Sanskrit Insight'})
            SET i.content = $fact, i.sanskrit_verse = $verse, i.translation = $translation
            MERGE (s)-[:HAS_SANSKRIT_INSIGHT]->(i)
        """, fact=data["fact"], verse=data["sanskrit_verse"], translation=data["translation"])
    print("Successfully pushed Sanskrit Insight to Neo4j for Part 2!")

if __name__ == "__main__":
    main()
