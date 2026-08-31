import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()
driver = GraphDatabase.driver(os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD")))

chap3_data = {
  "timeline_id": 3,
  "title": "Section II (Anukramanika Parva)",
  "summary": "Ugrasrava Sauti continues his address to the sages in the Naimisha forest. He outlines the vast structure of the Mahabharata, summarizing the major events, the divine origins of the characters, and the cosmic significance of the Kurukshetra war.",
  "characters": ["Sauti", "Saunaka", "Vyasa"],
  "locations": ["Naimisha Forest", "Kurukshetra"]
}

def push(tx, data):
    tx.run("MERGE (c:Chapter {timeline_id: $t}) SET c.summary=$s, c.title=$title", t=data["timeline_id"], s=data["summary"], title=data["title"])
    for char in data["characters"]:
        tx.run("MERGE (p:Character {name: $c}) WITH p MATCH (ch:Chapter {timeline_id: $t}) MERGE (ch)-[:MENTIONS_CHARACTER]->(p)", c=char, t=data["timeline_id"])
    for loc in data["locations"]:
        tx.run("MERGE (l:Location {name: $loc}) WITH l MATCH (ch:Chapter {timeline_id: $t}) MERGE (ch)-[:MENTIONS_LOCATION]->(l)", loc=loc, t=data["timeline_id"])

with driver.session() as session:
    session.execute_write(push, chap3_data)

print("Chapter 3 Pushed Successfully!")
driver.close()
