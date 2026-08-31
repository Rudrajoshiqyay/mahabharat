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
    res = session.run("MATCH (s:Section {global_id: $gid}) RETURN s.summary AS summary", gid=global_id)
    record = res.single()
    if not record or not record["summary"]: return
    
    prompt = f"""You are a Sanskrit expert. Extract EXACT verses from the bulk text matching the English summary.
    ENGLISH SUMMARY: {record['summary']}
    BULK SANSKRIT: {bulk_sanskrit}
    Output STRICT JSON: {{"fact": "...", "sanskrit_verse": "...", "translation": "..."}}
    """
    
    response = gemini_client.models.generate_content(
        model='gemini-3.6-flash',
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1)
    )
    
    data = json.loads(response.text.strip())
    session.run("MATCH (s:Section {global_id: $gid})-[r:HAS_SANSKRIT_INSIGHT]->(i:Insight) DETACH DELETE i", gid=global_id)
    session.run("""
        MATCH (s:Section {global_id: $gid})
        CREATE (i:Insight {type: 'Sanskrit Insight', content: $fact, sanskrit_verse: $verse, translation: $translation})
        MERGE (s)-[:HAS_SANSKRIT_INSIGHT]->(i)
    """, gid=global_id, fact=data["fact"], verse=data["sanskrit_verse"], translation=data["translation"])

def main():
    sanskrit = get_sanskrit_verses(1, 2)
    with db_driver.session() as session:
        process_semantic_match(session, "2_1", sanskrit)

if __name__ == "__main__":
    main()
