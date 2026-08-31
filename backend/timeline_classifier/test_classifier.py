import os
import sys
import re
from collections import Counter
from dotenv import load_dotenv
from neo4j import GraphDatabase

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv(dotenv_path="../../.env")

db_driver = GraphDatabase.driver(os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD")))

def get_word_frequencies(text):
    # Basic Bag-of-Words math (no LLM, no AI)
    words = re.findall(r'\w+', text.lower())
    # Filter out common stop words
    stop_words = {'the', 'and', 'to', 'of', 'a', 'in', 'was', 'by', 'for', 'with', 'on', 'as', 'at'}
    return Counter([w for w in words if w not in stop_words])

def classify_uploaded_text(session, user_text):
    print(f"\n==============================================")
    print(f"USER UPLOADS NEW TEXT:\n'{user_text}'")
    
    print("\nCalculating math (Bag-of-Words) for uploaded text...")
    user_freqs = get_word_frequencies(user_text)
    
    print("Asking Neo4j to find the exact timeline event using Keyword Overlap (No LLM)...")
    
    res = session.run("MATCH (s:Section) WHERE s.summary IS NOT NULL RETURN s.global_id AS gid, s.title AS title, s.summary AS summary")
    
    best_match = None
    highest_score = 0
    
    for record in res:
        section_freqs = get_word_frequencies(record["summary"])
        
        # Calculate overlap score (dot product of word frequencies)
        score = sum(user_freqs[word] * section_freqs.get(word, 0) for word in user_freqs)
        
        if score > highest_score:
            highest_score = score
            best_match = record
            
    if best_match:
        print(f"\n[CLASSIFICATION SUCCESS]")
        print(f"Matched Timeline Event: {best_match['title']} ({best_match['gid']})")
        print(f"Mathematical Overlap Score: {highest_score}")
    else:
        print("\n[NO MATCH FOUND] Text does not match any current timeline events.")
        
    print(f"==============================================\n")

if __name__ == "__main__":
    with db_driver.session() as session:
        # Test Case 1: Snake Sacrifice (Matches Section 2 Part 2 or 3)
        test_text_1 = "The terrifying snake sacrifice was held by King Janamejaya. Millions of serpents were drawn into the blazing fire by the mantras, until the wise Astika finally stopped the destruction."
        classify_uploaded_text(session, test_text_1)
        
        # Test Case 2: The Dice Game (Matches Section 2 Part 4)
        test_text_2 = "The wicked Shakuni rolled the dice with deceit. Yudhishthira, addicted to the game, lost his wealth, his brothers, and his kingdom, forcing them all to walk into the dark forest for twelve years."
        classify_uploaded_text(session, test_text_2)
