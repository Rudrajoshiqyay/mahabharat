import os
import json
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv(dotenv_path="../.env")
driver = GraphDatabase.driver(os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD")))

def clean_db(tx):
    # Delete any chapter with timeline_id >= 4 and its orphaned nodes
    tx.run("MATCH (c:Chapter) WHERE c.timeline_id >= 4 DETACH DELETE c")
    # Clean up characters/locations that have no relationships left
    tx.run("MATCH (n:Character) WHERE NOT (n)--() DELETE n")
    tx.run("MATCH (n:Location) WHERE NOT (n)--() DELETE n")

with driver.session() as session:
    session.execute_write(clean_db)

print("Cleaned up dummy data from database!")
driver.close()

# Also reset completed_ids
if os.path.exists("completed_ids.json"):
    with open("completed_ids.json", "w") as f:
        json.dump([1, 2, 3], f)
print("Reset checkpoint to Chapter 3")
