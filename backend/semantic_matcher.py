import os
import json
import sys
from dotenv import load_dotenv
from google import genai
from google.genai import types
from neo4j import GraphDatabase
from sanskrit_scraper import get_sanskrit_verses

sys.stdout.reconfigure(encoding='utf-8')

load_dotenv(dotenv_path="../.env")
gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
db_driver = GraphDatabase.driver(os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD")))

def process_semantic_match(session, global_id, bulk_sanskrit):
    # Get English Summary from Neo4j
    res = session.run("MATCH (s:Section {global_id: $gid}) RETURN s.summary AS summary", gid=global_id)
    record = res.single()
    if not record or not record["summary"]:
        print(f"Could not find English summary for {global_id}")
        return
    english_summary = record["summary"]
    
    print(f"\\n--- Processing {global_id} ---")
    
    prompt = f"""You are an expert in Sanskrit literature and the Mahabharata.
    Your task is to act as a highly precise semantic search engine.
    
    ENGLISH SUMMARY FOR THIS SPECIFIC SECTION:
    {english_summary}
    
    BULK SANSKRIT VERSES (Contains multiple chapters mixed together):
    {bulk_sanskrit}
    
    Instructions:
    1. Extract the EXACT Sanskrit verses from the bulk text that correspond to the meaning of the English summary.
    2. BE VERY PRECISE. If the English summary talks about "Sauti meeting the sages in Naimisha forest", you MUST find the verses containing the names Sauti, Saunaka, and Naimisha. DO NOT extract verses about the creation of the world or the primordial egg unless the summary explicitly focuses on that!
    3. Provide an accurate English translation of ONLY those extracted verses.
    4. Provide a highly interesting, mind-blowing fact about these specific Sanskrit verses.
    
    Output STRICT JSON:
    {{
        "fact": "The interesting fact...",
        "sanskrit_verse": "The extracted original sanskrit verses",
        "translation": "The direct English translation of the extracted verses"
    }}
    """
    
    print(f"Sending to Gemini for semantic matching...")
    response = gemini_client.models.generate_content(
        model='gemini-3.6-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.0
        )
    )
    
    try:
        data = json.loads(response.text.strip())
        print(f"Successfully matched verse! Fact: {data['fact'][:50]}...")
        
        # Update Neo4j
        session.run("""
            MATCH (s:Section {global_id: $gid})
            MATCH (s)-[r:HAS_SANSKRIT_INSIGHT]->(i:Insight)
            DETACH DELETE i
        """, gid=global_id)
        
        session.run("""
            MATCH (s:Section {global_id: $gid})
            CREATE (i:Insight {
                type: 'Sanskrit Insight',
                content: $fact,
                sanskrit_verse: $verse,
                translation: $translation
            })
            MERGE (s)-[:HAS_SANSKRIT_INSIGHT]->(i)
        """, gid=global_id, fact=data["fact"], verse=data["sanskrit_verse"], translation=data["translation"])
        print(f"Pushed matched Insight to Neo4j for {global_id}!")
    except Exception as e:
        print(f"Failed to parse or push: {e}")
        print("Raw response:", response.text)


def main():
    print("Fetching bulk Sanskrit verses...")
    sanskrit_1_1 = get_sanskrit_verses(1, 1)
    sanskrit_1_2 = get_sanskrit_verses(1, 2)
    
    bulk_sanskrit = f"--- SOURCE 1.1 ---\\n{sanskrit_1_1}\\n--- SOURCE 1.2 ---\\n{sanskrit_1_2}"
    
    with db_driver.session() as session:
        # Match for 1_1
        process_semantic_match(session, "1_1", bulk_sanskrit)
        # Match for 1_2
        process_semantic_match(session, "1_2", bulk_sanskrit)
        
    print("Semantic matching completed successfully!")

if __name__ == "__main__":
    main()
