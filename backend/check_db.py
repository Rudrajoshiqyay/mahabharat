import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()
URI = os.getenv("NEO4J_URI")
USERNAME = os.getenv("NEO4J_USERNAME")
PASSWORD = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))
with driver.session() as session:
    result = session.run("MATCH (c:Chapter) RETURN c.timeline_id ORDER BY c.timeline_id DESC LIMIT 10")
    ids = []
    for record in result:
        val = record[0]
        if hasattr(val, 'low'):
            ids.append(val.low)
        else:
            ids.append(val)
    print(f"Latest Chapters in Database: {ids}")
driver.close()
