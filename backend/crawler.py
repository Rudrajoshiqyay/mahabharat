import os
import json
import time
from dotenv import load_dotenv
from apify_client import ApifyClient
from groq import Groq
from neo4j import GraphDatabase

load_dotenv(dotenv_path="../.env")
apify_client = ApifyClient(os.getenv("APIFY_API_TOKEN"))
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
db_driver = GraphDatabase.driver(os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD")))

with open("book1_queue.json", "r", encoding="utf-8") as f:
    book_tree = json.load(f)

checkpoint_path = "completed_sections.json"
if os.path.exists(checkpoint_path):
    with open(checkpoint_path, "r") as f:
        completed = json.load(f)
else:
    completed = []

def push_to_neo4j(book_title, parva_title, section_data, extracted):
    def create_nodes(tx):
        # 1. Create Hierarchy
        tx.run("""
            MERGE (b:Book {title: $b_title})
            MERGE (p:Parva {title: $p_title})
            MERGE (b)-[:CONTAINS]->(p)
        """, b_title=book_title, p_title=parva_title)
        
        # 2. Create Section
        tx.run("""
            MERGE (p:Parva {title: $p_title})
            MERGE (s:Section {global_id: $s_id})
            SET s.title = $s_title, s.summary = $summary, s.url = $url
            MERGE (p)-[:CONTAINS]->(s)
        """, p_title=parva_title, s_id=section_data["global_id"], s_title=section_data["title"], summary=extracted.get("summary", ""), url=section_data["url"])
        
        # 3. Create Characters
        for char in extracted.get("characters", []):
            name = char.get("name", "")
            context = char.get("context", "")
            if not name: continue
            tx.run("""
                MERGE (c:Character {name: $name})
                MERGE (s:Section {global_id: $s_id})
                MERGE (s)-[r:MENTIONS_CHARACTER]->(c)
                SET r.context = $context
            """, name=name, s_id=section_data["global_id"], context=context)
            
        # 4. Create Locations
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

    with db_driver.session() as session:
        session.execute_write(create_nodes)

print("Starting Hierarchical Storybook Crawler...")

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
            
        print(f"\n--- Processing [{section['title']}]: {parva['title']} -> {section['title']} ---", flush=True)
        
        # A. SCRAPE
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

        # Chunking to avoid Groq TPM Rate Limits and context limits (User requested 'parts')
        chunk_size = 4000
        chunks = [raw_text[i:i+chunk_size] for i in range(0, len(raw_text), chunk_size)]
        
        for part_idx, chunk_text in enumerate(chunks):
            part_num = part_idx + 1
            part_title = f"{section['title']} (Part {part_num})"
            part_global_id = f"{s_id}_{part_num}"
            
            print(f"  -> Processing {part_title}...", flush=True)

            # B. GROQ EXTRACTION
            prompt = f"""You are an expert storyteller and historian. Read the following text from the Mahabharata carefully.
            
            Extract the information into STRICT JSON format. Do NOT output markdown ticks or conversational text.
            
            Rules for the summary:
            - Provide a highly detailed, comprehensive narrative of the events in this specific section.
            - Preserve the exact sequence of events, important dialogues, and character actions. Do not change the meaning.
            - Naturally introduce characters with brief context if they are new or important (e.g., 'Vyasa, the author of the epic, arrived...').
            - Naturally explain locations in modern terms (e.g. 'Naimisha forest, located in modern-day Uttar Pradesh') to help modern audiences understand.
            - The summary should read like a rich storybook.
            
            Rules for extraction arrays:
            - If a character is introduced, provide a brief 'context'. Leave blank if minor or previously well known.
            - For locations, provide modern geographical context or historical significance so modern audiences understand where it is.
            
            Required JSON Schema:
            {{
                "summary": "Write the highly detailed, continuous story summary here...",
                "characters": [
                    {{"name": "Real Name", "context": "Brief context or blank"}}
                ],
                "locations": [
                    {{"name": "Real Location Name", "context": "Modern geographical context or historical significance"}}
                ]
            }}
            
            Text to extract from: {chunk_text}"""
            
            import re
            success = False
            extracted_json = None
            attempt = 0
            while attempt < 5:
                try:
                    completion = groq_client.chat.completions.create(
                        model="openai/gpt-oss-20b",
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.3,
                        max_tokens=2500
                    )
                    
                    text_out = completion.choices[0].message.content.strip()
                    if not text_out:
                        raise ValueError("AI returned an empty string")
                        
                    # Robust JSON extraction: Bracket counting
                    start_idx = text_out.find("{")
                    if start_idx != -1:
                        brackets = 0
                        for i in range(start_idx, len(text_out)):
                            if text_out[i] == "{": brackets += 1
                            elif text_out[i] == "}": brackets -= 1
                            if brackets == 0:
                                extracted_json = json.loads(text_out[start_idx:i+1])
                                break
                                
                    if not extracted_json:
                        # Attempt to force-close JSON.
                        if "{" in text_out and not text_out.endswith("}"):
                            try:
                                end_quote = text_out.rfind('"')
                                cleaned = text_out[:end_quote+1] + '], "locations": []}'
                                extracted_json = json.loads(cleaned)
                            except:
                                pass
                                
                    if extracted_json:
                        break
                    else:
                        raise ValueError(f"Failed to parse JSON. Raw output: {text_out[:200]}")
                        
                except Exception as e:
                    safe_error = str(e).encode('ascii', 'replace').decode('ascii')
                    
                    # DYNAMIC RATE LIMIT SLEEPER
                    if "Please try again in" in safe_error:
                        match = re.search(r"try again in (?:(\d+)h)?(?:(\d+)m)?(?:([\d.]+)s)?", safe_error)
                        if match:
                            h = int(match.group(1)) if match.group(1) else 0
                            m = int(match.group(2)) if match.group(2) else 0
                            s = float(match.group(3)) if match.group(3) else 0
                            wait_s = (h * 3600) + (m * 60) + s + 5 # 5s buffer
                            print(f"  [Rate Limit] Daily quota hit. Pausing crawler for {wait_s/60:.1f} minutes...", flush=True)
                            time.sleep(wait_s)
                            continue # retry without incrementing attempt
                    
                    print(f"  [Error] Groq Error (Attempt {attempt+1}/5): {safe_error[:150]}", flush=True)
                    attempt += 1
                    time.sleep(5)
            
            # ULTIMATE FALLBACK: If all 3 attempts fail, DO NOT save an empty string! Save the raw scraped text!
            if not extracted_json:
                print(f"  [Warning] All 3 attempts failed. Falling back to raw scraped text for {part_title}!", flush=True)
                extracted_json = {
                    "summary": f"[AI Summary Failed. Raw Text:]\n\n{chunk_text}",
                    "characters": [],
                    "locations": []
                }
                
            # Override section data for this specific part
            part_section_data = {
                "global_id": part_global_id,
                "title": part_title,
                "url": section["url"]
            }
            
            push_to_neo4j(book_tree["title"], parva["title"], part_section_data, extracted_json)
            success = True
            print(f"  [OK] Successfully extracted and pushed {part_title} to Neo4j!", flush=True)
                    
            print("  [Sleep] Waiting 15s to respect Groq Tokens-Per-Minute rate limits...", flush=True)
            time.sleep(15)
            
        if success:
            completed.append(s_id)
            with open(checkpoint_path, "w") as f:
                json.dump(completed, f)

db_driver.close()
print("Book 1 Finished!")
