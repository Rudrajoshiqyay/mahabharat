import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()
URI = os.getenv("NEO4J_URI")
USERNAME = os.getenv("NEO4J_USERNAME")
PASSWORD = os.getenv("NEO4J_PASSWORD")
driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))

chap2_data = {
  "timeline_id": 2,
  "title": "Section I (Adivansavatarana Parva)",
  "summary": "Sauti approaches the sages in the forest of Naimisha and begins to recount the great epic of the Mahabharata, originally composed by Vyasa, detailing the origins of the universe and the divine lineages.",
  "characters": ["Sauti", "Saunaka", "Vyasa", "Bhrigu", "Brahma"],
  "locations": ["Naimisha Forest", "Samantapanchaka"]
}

def push(tx, data):
    tx.run("MERGE (c:Chapter {timeline_id: $t}) SET c.summary=$s, c.title=$title", t=data["timeline_id"], s=data["summary"], title=data["title"])
    for char in data["characters"]:
        tx.run("MERGE (p:Character {name: $c}) WITH p MATCH (ch:Chapter {timeline_id: $t}) MERGE (ch)-[:MENTIONS_CHARACTER]->(p)", c=char, t=data["timeline_id"])
    for loc in data["locations"]:
        tx.run("MERGE (l:Location {name: $loc}) WITH l MATCH (ch:Chapter {timeline_id: $t}) MERGE (ch)-[:MENTIONS_LOCATION]->(l)", loc=loc, t=data["timeline_id"])

with driver.session() as session:
    session.execute_write(push, chap2_data)

print("Chapter 2 Pushed Successfully!")
driver.close()
