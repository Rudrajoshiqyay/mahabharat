import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()
URI = os.getenv("NEO4J_URI")
USERNAME = os.getenv("NEO4J_USERNAME")
PASSWORD = os.getenv("NEO4J_PASSWORD")

# The exact JSON data Gemini just output
test_data = {
  "timeline_id": 1,
  "summary": "Kisari Mohan Ganguli outlines his philosophy of producing a faithful and literal English translation of Vyasa's Mahabharata rather than adapting it to English tastes.",
  "characters": ["Krishna-Dwaipayana Vyasa", "Kauravas", "Pandavas", "Kisari Mohan Ganguli"],
  "locations": ["India", "Bengal", "Calcutta"]
}

print("Connecting to Neo4j...")
driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))

def create_graph_nodes(tx, data):
    # 1. Create the Chapter Event Node
    tx.run("""
    MERGE (c:Chapter {timeline_id: $timeline_id})
    SET c.summary = $summary
    """, timeline_id=data["timeline_id"], summary=data["summary"])

    # 2. Create Characters and link them to the chapter
    for char in data["characters"]:
        tx.run("""
        MERGE (p:Character {name: $char})
        WITH p
        MATCH (c:Chapter {timeline_id: $timeline_id})
        MERGE (c)-[:MENTIONS_CHARACTER]->(p)
        """, char=char, timeline_id=data["timeline_id"])

    # 3. Create Locations and link them
    for loc in data["locations"]:
        tx.run("""
        MERGE (l:Location {name: $loc})
        WITH l
        MATCH (c:Chapter {timeline_id: $timeline_id})
        MERGE (c)-[:MENTIONS_LOCATION]->(l)
        """, loc=loc, timeline_id=data["timeline_id"])

with driver.session() as session:
    session.execute_write(create_graph_nodes, test_data)

print("SUCCESS! Nodes pushed to Neo4j.")
driver.close()
