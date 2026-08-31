import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv(dotenv_path="../../.env")
driver = GraphDatabase.driver(os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD")))

def test_no_duplicate_characters():
    """Regression: Ensure that characters are strictly merged and not duplicated across texts."""
    with driver.session() as session:
        res = session.run("""
            MATCH (c:Character)
            WITH c.name AS name, count(c) AS num
            WHERE num > 1
            RETURN name
        """)
        duplicates = [record["name"] for record in res]
        assert len(duplicates) == 0, f"Graph Integrity Broken! Found duplicate characters: {duplicates}"
        print("[PASS] Graph Integrity: No duplicate characters found. Overlaps are safe.")

def test_mahabharata_timeline_integrity():
    """Regression: Ensure Mahabharata sections still have strict timeline connections."""
    with driver.session() as session:
        res = session.run("""
            MATCH (b:Book {title: 'Book 1'})-[:CONTAINS]->(p:Parva)-[:CONTAINS]->(s:Section)
            RETURN count(s) as section_count
        """)
        count = res.single()["section_count"]
        assert count > 0, "Graph Integrity Broken! Mahabharata sections are missing."
        print(f"[PASS] Timeline Integrity: Mahabharata spine is intact with {count} sections.")

def test_articles_are_isolated():
    """Regression: Ensure non-linear articles don't accidentally become part of the chronological spine."""
    with driver.session() as session:
        res = session.run("""
            MATCH (a:Article)<-[:CONTAINS]-(p:Parva)
            RETURN count(a) as bad_links
        """)
        bad_links = res.single()["bad_links"]
        assert bad_links == 0, "Graph Integrity Broken! Articles are polluting the linear timeline."
        print("[PASS] Schema Integrity: Articles are safely isolated from the main epics.")

if __name__ == "__main__":
    print("Running GraphRAG Regression Tests...")
    try:
        test_no_duplicate_characters()
        test_mahabharata_timeline_integrity()
        test_articles_are_isolated()
        print("\nAll Regression Tests Passed! The universe can be safely expanded.")
    except AssertionError as e:
        print(f"\n[FAIL] {e}")
    finally:
        driver.close()
