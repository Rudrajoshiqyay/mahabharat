import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv(dotenv_path="../.env")
driver = GraphDatabase.driver(os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD")))

def wipe_db(tx):
    tx.run("MATCH (n) DETACH DELETE n")

with driver.session() as session:
    session.execute_write(wipe_db)

print("Wiped database completely for new Book > Parva > Section schema.")
driver.close()
