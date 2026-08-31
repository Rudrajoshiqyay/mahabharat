import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types
from neo4j import GraphDatabase

load_dotenv(dotenv_path="../.env")
gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
db_driver = GraphDatabase.driver(os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD")))

def main():
    prompt = """You are an expert in Sanskrit literature and the Mahabharata.
    Provide a highly interesting, mind-blowing fact about the opening Sanskrit invocation of the Mahabharata (Section 1.1) which starts with 'नारायणं नमस्कृत्य नरं चैव नरोत्तमम्'.
    Explain the profound philosophical, linguistic, or cultural significance of these specific Sanskrit words and how they relate directly to the core themes of the Mahabharata.
    Output STRICT JSON: 
    { 
        "fact": "The interesting fact...", 
        "sanskrit_verse": "नारायणं नमस्कृत्य नरं चैव नरोत्तमम् । देवीं सरस्वतीं चैव ततो जयमुदीरयेत् ॥", 
        "translation": "Having bowed down to Narayana and Nara, the most exalted male being, and also to the goddess Sarasvati, must the word Jaya be uttered." 
    }"""
    
    response = gemini_client.models.generate_content(
        model='gemini-3.6-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.3
        )
    )
    data = json.loads(response.text.strip())
    
    with db_driver.session() as session:
        session.run("""
            MATCH (s:Section {global_id: '1_1'})
            MERGE (i:Insight {type: 'Sanskrit Insight', content: $fact})
            SET i.sanskrit_verse = $verse, i.translation = $translation
            MERGE (s)-[:HAS_SANSKRIT_INSIGHT]->(i)
        """, fact=data["fact"], verse=data["sanskrit_verse"], translation=data["translation"])
    print("Successfully pushed Sanskrit Insight to Neo4j!")

if __name__ == "__main__":
    main()
