import os
import sys
import json
import re
from collections import Counter
from dotenv import load_dotenv
from neo4j import GraphDatabase

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv(dotenv_path="../.env")

db_driver = GraphDatabase.driver(os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD")))

def get_word_frequencies(text):
    words = re.findall(r'\w+', text.lower())
    stop_words = {'the', 'and', 'to', 'of', 'a', 'in', 'was', 'by', 'for', 'with', 'on', 'as', 'at', 'is', 'it', 'from', 'this', 'that'}
    return Counter([w for w in words if w not in stop_words])

def classify_draft(draft_path):
    if not os.path.exists(draft_path):
        print("No draft found.")
        return None
        
    with open(draft_path, "r", encoding="utf-8") as f:
        draft_data = json.load(f)
        
    summary = draft_data.get("summary", "")
    if not summary:
        print("Draft has no summary.")
        return None
        
    print("Classifying source type and finding mathematical anchor (Zero-LLM Math)...")
    user_freqs = get_word_frequencies(summary)
    
    best_match = None
    highest_score = 0
    
    with db_driver.session() as session:
        res = session.run("MATCH (s:Section) WHERE s.summary IS NOT NULL RETURN s.global_id AS gid, s.title AS title, s.summary AS summary")
        for record in res:
            section_freqs = get_word_frequencies(record["summary"])
            score = sum(user_freqs[word] * section_freqs.get(word, 0) for word in user_freqs)
            
            if score > highest_score:
                highest_score = score
                best_match = record

    # Zero-LLM Chronology Check (Check for Pre-Mahabharata/Creation keywords)
    pre_mahabharata_keywords = {'creation', 'brahma', 'universe', 'satya', 'yuga', 'treta', 'matsya', 'kurma', 'varaha', 'narasimha', 'vamana', 'planets', 'cosmos', 'creator'}
    pre_score = sum(user_freqs.get(kw, 0) for kw in pre_mahabharata_keywords)
    
    if pre_score > 0.05: # Threshold for creation/epoch texts
        draft_data["classification"] = {
            "type": "Cosmological / Pre-Mahabharata Epoch",
            "matched_event": "Creation & Early Yugas (Pre-Adi Parva)",
            "matched_gid": "PRE_0",
            "matched_summary": "This text describes events that occurred before the primary Mahabharata timeline, such as cosmological creation, early avatars, or planetary systems. It will be anchored to the root 'Absolute Time' node.",
            "mathematical_overlap_score": int(pre_score * 1000)
        }
    elif best_match:
        doc_type = "Core Text Addendum" if highest_score > 30 else "Non-Linear Article"
        
        draft_data["classification"] = {
            "type": doc_type,
            "matched_event": best_match["title"],
            "matched_gid": best_match["gid"],
            "matched_summary": best_match["summary"],
            "mathematical_overlap_score": highest_score
        }
    else:
        draft_data["classification"] = {"type": "Unknown", "matched_event": "None"}
            
    with open(draft_path, "w", encoding="utf-8") as f:
        json.dump(draft_data, f, indent=4)
        
    print(f"Classification appended to {draft_path}")
    print(json.dumps(draft_data["classification"], indent=2))

if __name__ == "__main__":
    classify_draft("draft_upload.json")
