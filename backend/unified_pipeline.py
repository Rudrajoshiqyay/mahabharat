import os
import json
import time
import sys
from dotenv import load_dotenv
from apify_client import ApifyClient
from groq import Groq
from google import genai
from google.genai import types
from neo4j import GraphDatabase
from sanskrit_scraper import get_sanskrit_verses

sys.stdout.reconfigure(encoding='utf-8')

load_dotenv(dotenv_path="../.env")
apify_client = ApifyClient(os.getenv("APIFY_API_TOKEN"))
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
db_driver = GraphDatabase.driver(os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD")))

def update_pipeline_state(status, message="", halted_at=""):
    state = {"status": status, "message": message, "halted_at": halted_at}
    with open("pipeline_state.json", "w") as f:
        json.dump(state, f)
    print(f"\n[PIPELINE STATE] {status}: {message}")

def push_english_to_neo4j(book_title, parva_title, section_data, extracted):
    def create_nodes(tx):
        tx.run("""
            MERGE (b:Book {title: $book_title})
            MERGE (p:Parva {title: $parva_title})
            MERGE (s:Section {global_id: $global_id})
            SET s.title = $title,
                s.url = $url,
                s.summary = $summary,
                s.brief_summary = $brief_summary,
                s.next_part_impact = $next_part_impact
            MERGE (b)-[:CONTAINS]->(p)
            MERGE (p)-[:CONTAINS]->(s)
        """, book_title=book_title, parva_title=parva_title, global_id=section_data["global_id"], 
             title=section_data["title"], url=section_data.get("url", ""), summary=extracted.get("summary", ""),
             brief_summary=extracted.get("brief_summary", ""), next_part_impact=extracted.get("next_part_impact", ""))

        for char in extracted.get("characters", []):
            if isinstance(char, str): char = {"name": char, "context": ""}
            name = char.get("name", "")
            context = char.get("context", "")
            if not name: continue
            tx.run("""
                MERGE (c:Character {name: $name})
                MERGE (s:Section {global_id: $s_id})
                MERGE (s)-[r:MENTIONS_CHARACTER]->(c)
                SET r.context = $context
            """, name=name, s_id=section_data["global_id"], context=context)
            
        for loc in extracted.get("locations", []):
            if isinstance(loc, dict):
                l_name = loc.get("name", "")
                l_context = loc.get("context", "")
            else:
                l_name = loc
                l_context = ""
            if not l_name: continue
            tx.run("""
                MERGE (l:Location {name: $l_name})
                MERGE (s:Section {global_id: $s_id})
                MERGE (s)-[r:MENTIONS_LOCATION]->(l)
                SET r.context = $context
            """, l_name=l_name, s_id=section_data["global_id"], context=l_context)

        for term_obj in extracted.get("glossary", []):
            if isinstance(term_obj, str): term_obj = {"term": term_obj}
            term = term_obj.get("term", "")
            def_in = term_obj.get("definition_indian", "")
            def_intl = term_obj.get("definition_international", "")
            root = term_obj.get("sanskrit_root", "")
            meaning = term_obj.get("root_meaning", "")
            if not term: continue
            tx.run("""
                MERGE (g:GlossaryTerm {term: $term})
                MERGE (s:Section {global_id: $s_id})
                MERGE (s)-[r:MENTIONS_TERM]->(g)
                SET g.definition_indian = $def_in, g.definition_international = $def_intl, g.sanskrit_root = $root, g.root_meaning = $meaning
            """, term=term, s_id=section_data["global_id"], def_in=def_in, def_intl=def_intl, root=root, meaning=meaning)

        for lore in extracted.get("mind_blowing_lore", []):
            if isinstance(lore, str): lore = {"topic": lore[:50], "fact": lore, "type": "Fact"}
            topic = lore.get("topic", "")
            fact = lore.get("fact", "")
            lore_type = lore.get("type", "")
            if not topic: continue
            tx.run("""
                MERGE (f:Fact {topic: $topic, content: $fact})
                SET f.type = $lore_type, f.source = 'Mahabharata Lore'
                MERGE (s:Section {global_id: $s_id})
                MERGE (s)-[:HAS_LORE]->(f)
            """, topic=topic, fact=fact, lore_type=lore_type, s_id=section_data["global_id"])

    with db_driver.session() as session:
        session.execute_write(create_nodes)

def run_semantic_match(global_id, english_summary, section_num):
    print(f"  -> Scraping Sanskrit Candidate verses for semantic match (Window: {section_num}, {section_num+1})...", flush=True)
    sanskrit_1 = get_sanskrit_verses(1, section_num)
    sanskrit_2 = get_sanskrit_verses(1, section_num + 1)
    bulk_sanskrit = f"--- SANSKRIT PART {section_num} ---\\n{sanskrit_1}\\n--- SANSKRIT PART {section_num+1} ---\\n{sanskrit_2}"
    
    prompt = f"""You are a Sanskrit scholar.
    ENGLISH SUMMARY FOR SECTION {global_id}:
    {english_summary}
    
    BULK SANSKRIT VERSES:
    {bulk_sanskrit}
    
    Extract the EXACT Sanskrit verses matching the summary. Provide translation and a mind-blowing fact.
    IF there is NO matching verse in this text, output an empty JSON object: {{}}
    OTHERWISE, Output STRICT JSON: {{"fact": "...", "sanskrit_verse": "...", "translation": "..."}}
    """
    
    print("  -> Asking Gemini for semantic match...", flush=True)
    
    for attempt in range(5):
        try:
            response = gemini_client.models.generate_content(
                model='gemini-3.6-flash',
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1)
            )
            data = json.loads(response.text.strip())
            
            if not data or "sanskrit_verse" not in data:
                return False, "No matching verse found in the candidate pool."
                
            with db_driver.session() as session:
                session.run("MATCH (s:Section {global_id: $gid})-[r:HAS_SANSKRIT_INSIGHT]->(i:Insight) DETACH DELETE i", gid=global_id)
                session.run("""
                    MATCH (s:Section {global_id: $gid})
                    CREATE (i:Insight {type: 'Sanskrit Insight', content: $fact, sanskrit_verse: $verse, translation: $translation})
                    MERGE (s)-[:HAS_SANSKRIT_INSIGHT]->(i)
                """, gid=global_id, fact=data["fact"], verse=data["sanskrit_verse"], translation=data["translation"])
                
            print("  [OK] Successfully pushed Sanskrit match to Neo4j!", flush=True)
            return True, "Success"
        except Exception as e:
            error_str = str(e)
            print(f"  [Error] {error_str}", flush=True)
            time.sleep(15) # Wait out the rate limit
    
    return False, "Failed after 5 retries (Gemini rate limit)"


def main():
    update_pipeline_state("RUNNING", "Starting unified pipeline")
    
    with open("book1_queue.json", "r", encoding="utf-8") as f:
        book_tree = json.load(f)

    checkpoint_path = "completed_sections.json"
    if os.path.exists(checkpoint_path):
        with open(checkpoint_path, "r") as f:
            completed = json.load(f)
    else:
        completed = []

    for parva in book_tree["parvas"]:
        for section in parva["sections"]:
            s_id = section["global_id"]
            if s_id in completed:
                continue
                
            print(f"\\n=== Processing [{section['title']}] ===", flush=True)
            
            try:
                run = apify_client.actor("apify/cheerio-scraper").call(run_input={
                    "startUrls": [{"url": section["url"]}],
                    "pageFunction": "async function pageFunction(context) { return { text: context.$('.text-body').text().replace(/\\s+/g, ' ').trim() || context.$('body').text().replace(/\\s+/g, ' ').trim() }; }"
                })
                dataset_id = getattr(run, 'default_dataset_id', getattr(run, 'defaultDatasetId', None))
                if not dataset_id: dataset_id = run.model_dump().get("defaultDatasetId", run.model_dump().get("default_dataset_id"))
                raw_text = next(apify_client.dataset(dataset_id).iterate_items(), {}).get("text", "")
                if not raw_text: continue
            except Exception as e:
                print(f"Apify Error: {e}", flush=True)
                time.sleep(5)
                continue

            chunk_size = 4000
            chunks = [raw_text[i:i+chunk_size] for i in range(0, len(raw_text), chunk_size)]
            
            for part_idx, chunk_text in enumerate(chunks):
                part_num = part_idx + 1
                part_global_id = f"{s_id}_{part_num}"
                part_title = f"{section['title']} (Part {part_num})"
                
                print(f"\\n  --- Chunk {part_global_id} ---", flush=True)
                
                prompt = f'''You are an expert storyteller and historian. Read the following text from the Mahabharata carefully.
        Extract the information into STRICT JSON format. Do NOT output markdown ticks or conversational text.
        - CRITICAL: Ensure characters and locations are spelled exactly as they appear.
        - CRITICAL: For locations, do NOT guess the modern geographical context if you are not 100% certain. 
        - If you are unsure of the modern equivalent, simply provide the historical context from the text and leave the modern location blank.
        - LORE: Identify 0 to 2 genuinely mind-blowing, lesser-known facts or obscure folklore connected to the events/locations in this part.
        - GLOSSARY: For every glossary term, provide the original Sanskrit root word in Devanagari, and its direct literal English meaning.
        Required JSON Schema:
        {{
            "brief_summary": "A 1-line recap of what happened in this specific part.",
            "next_part_impact": "A 1-line explanation of how the events in this part will affect or set up the next part.",
            "summary": "Write the highly detailed, continuous story summary here...",
            "characters": [ {{"name": "Real Name", "context": "Brief context or blank"}} ],
            "locations": [ {{"name": "Real Location Name", "context": "Modern geographical context ONLY if 100% certain, otherwise historical significance"}} ],
            "glossary": [ {{"term": "Sanskrit/Cultural Term", "sanskrit_root": "Original Devanagari root word", "root_meaning": "Direct literal translation of the root word", "definition_indian": "Definition for Indian audience", "definition_international": "Simplified definition for international audience"}} ],
            "mind_blowing_lore": [ {{"topic": "The specific phrase/word in the summary to highlight", "fact": "The mind-blowing obscure folklore/legend", "type": "Legend/Folklore"}} ]
        }}
        English Text to extract from: {chunk_text}'''
                
                extracted_json = None
                for attempt in range(5):
                    try:
                        if attempt == 0:
                            response = gemini_client.models.generate_content(
                                model='gemini-3.6-flash',
                                contents=prompt,
                                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0)
                            )
                            extracted_json = json.loads(response.text)
                        else:
                            print(f"  [Warning] Gemini failed. Failing over to Groq openai/gpt-oss-120b (Attempt {attempt+1}/5)...", flush=True)
                            response = groq_client.chat.completions.create(
                                model="openai/gpt-oss-120b",
                                messages=[{"role": "user", "content": prompt}],
                                response_format={"type": "json_object"},
                                temperature=0
                            )
                            extracted_json = json.loads(response.choices[0].message.content)
                        break
                    except Exception as e:
                        print(f"  [Error] English extraction attempt {attempt+1} failed: {e}")
                        time.sleep(5)
                
                if not extracted_json or not isinstance(extracted_json, dict):
                    extracted_json = { "summary": chunk_text, "characters": [], "locations": [], "glossary": [], "mind_blowing_lore": [] }
                
                push_english_to_neo4j(book_tree["title"], parva["title"], {"global_id": part_global_id, "title": part_title, "url": section["url"]}, extracted_json)
                print(f"  [OK] Saved English rich text to Neo4j.", flush=True)
                
                success, error_msg = run_semantic_match(part_global_id, extracted_json["summary"], s_id)
                
                if not success:
                    update_pipeline_state("HALTED", f"Failed to match Sanskrit for {part_global_id}: {error_msg}", halted_at=part_global_id)
                    print(f"\\n[!] PIPELINE HALTED AT {part_global_id} [!]")
                    sys.exit(1)
                
                time.sleep(15)
                
            completed.append(s_id)
            with open(checkpoint_path, "w") as f:
                json.dump(completed, f)
                
    update_pipeline_state("FINISHED", "All sections completed successfully.")
    print("Pipeline Finished!")

if __name__ == "__main__":
    main()
