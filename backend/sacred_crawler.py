import os
import json
import time
from urllib.parse import urljoin
from dotenv import load_dotenv
from apify_client import ApifyClient
from google import genai
from google import genai
from google.genai import types
from neo4j import GraphDatabase

from groq import Groq
from sanskrit_scraper import get_sanskrit_verses

load_dotenv(dotenv_path="../.env")
apify_client = ApifyClient(os.getenv("APIFY_API_TOKEN"))
gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
db_driver = GraphDatabase.driver(os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD")))

def push_to_neo4j(book_title, parva_title, section_data, extracted):
    def create_nodes(tx):
        # Merge Parva and Section nodes
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

        # 1. Characters
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

        # 5. Create Glossary Terms
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

        # 6. Create Lore Facts
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
            
        # 7. Create Sanskrit Insight
        sans = extracted.get("sanskrit_insight", {})
        if sans and isinstance(sans, dict) and sans.get("fact"):
            tx.run("""
                MERGE (s:Section {global_id: $s_id})
                MERGE (i:Insight {type: 'Sanskrit Insight', content: $fact})
                SET i.sanskrit_verse = $verse, i.translation = $translation
                MERGE (s)-[:HAS_SANSKRIT_INSIGHT]->(i)
            """, s_id=section_data["global_id"], fact=sans.get("fact"), verse=sans.get("sanskrit_verse", ""), translation=sans.get("translation", ""))

    with db_driver.session() as session:
        session.execute_write(create_nodes)

print("Starting Sacred-Texts Linear Crawler (Hybrid Gemini/Groq Edition)...")

current_url = "https://sacred-texts.com/hin/m01/m01002.htm"
global_section_id = 1

while current_url:
    print(f"\\n--- Scraping {current_url} ---", flush=True)
    
    # A. SCRAPE
    try:
        run = apify_client.actor("apify/cheerio-scraper").call(run_input={
            "startUrls": [{"url": current_url}],
            "pageFunction": '''async function pageFunction(context) {
                const $ = context.$;
                let nextLink = null;
                $('a').each(function() {
                    if ($(this).text().toLowerCase().includes('next:')) {
                        nextLink = $(this).attr('href');
                    }
                });
                return {
                    title: $('title').text(),
                    h1: $('h1').text(),
                    nextLink: nextLink,
                    text: $('body').text().replace(/\\s+/g, ' ').trim()
                };
            }'''
        })
        dataset_id = getattr(run, 'default_dataset_id', getattr(run, 'defaultDatasetId', None)) or run.model_dump().get("defaultDatasetId")
        item = next(apify_client.dataset(dataset_id).iterate_items(), {})
        
        raw_text = item.get("text", "")
        title_tag = item.get("title", "")
        next_rel_link = item.get("nextLink")
        
        if not raw_text:
            print("Failed to get text", flush=True)
            break
            
    except Exception as e:
        print(f"Apify Error: {e}", flush=True)
        time.sleep(5)
        continue

    # Parse title
    parva_title = "Adi Parva"
    section_title = f"Section {global_section_id}"
    book_title = "Book 1"
    
    parts = title_tag.split(":")
    if len(parts) >= 3:
        parva_title = parts[1].strip()
        sec = parts[2].split("|")[0].strip()
        if "Section" in sec:
            section_title = sec
            
    print(f"Parsed -> Parva: {parva_title}, Section: {section_title}")
    
    # 2. Scrape corresponding original Sanskrit via Apify Cheerio
    sanskrit_url = f"https://sanskritsahitya.org/mahabharatam/1.{global_section_id}"
    print(f"  -> Fetching original Sanskrit from {sanskrit_url}...")
    
    clean_url = sanskrit_url.replace("https://", "")
    
    apify_input = {
        "startUrls": [{"url": f"https://{clean_url}"}],
        "keepUrlFragments": False,
        "linkSelector": "",
        "pseudoUrls": [],
        "pageFunction": """
            async function pageFunction(context) {
                const { $ } = context;
                return {
                    text: $('body').text()
                };
            }
        """,
        "proxyConfiguration": {"useApifyProxy": True}
    }
    
    try:
        run = apify_client.actor("apify/cheerio-scraper").call(run_input=apify_input)
        dataset_id = getattr(run, 'default_dataset_id', getattr(run, 'defaultDatasetId', None)) or run.model_dump().get("defaultDatasetId")
        sanskrit_items = list(apify_client.dataset(dataset_id).iterate_items())
        raw_sanskrit_html_text = ""
        if sanskrit_items:
            raw_sanskrit_text = sanskrit_items[0].get("text", "")
            import re
            devanagari_lines = [line.strip() for line in raw_sanskrit_text.split('\n') if re.search(r'[\u0900-\u097F]', line)]
            raw_sanskrit_html_text = '\n'.join(devanagari_lines)
            print(f"  [OK] Retrieved {len(raw_sanskrit_html_text)} chars of Sanskrit.")
        else:
            print("  [Warning] Failed to fetch Sanskrit.")
    except Exception as e:
        print(f"  [Error] Apify Sanskrit extraction failed: {e}")
        raw_sanskrit_html_text = ""
    
    # Chunking
    chunk_size = 4000
    chunks = [raw_text[i:i+chunk_size] for i in range(0, len(raw_text), chunk_size)]
    
    used_sanskrit_verses = []
    
    for part_idx, chunk_text in enumerate(chunks):
        part_num = part_idx + 1
        part_title = f"{section_title} (Part {part_num})"
        part_global_id = f"{global_section_id}_{part_num}"
        
        print(f"  -> Processing {part_title} (English Agent)...", flush=True)

        prompt_1 = f'''You are an expert storyteller and historian. Read the following text from the Mahabharata carefully.
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
        attempt = 0
        while attempt < 5:
            try:
                if attempt < 1:
                    response = gemini_client.models.generate_content(
                        model='gemini-3.6-flash',
                        contents=prompt_1,
                        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0)
                    )
                    extracted_json = json.loads(response.text)
                    print("  [OK] English Extraction successful via Gemini")
                    break
                else:
                    if attempt == 1: print("  [Warning] Gemini Rate Limit hit! Failing over to Groq (Attempt 1/5)...")
                    response = groq_client.chat.completions.create(
                        model="openai/gpt-oss-120b",
                        messages=[{"role": "user", "content": prompt_1}],
                        response_format={"type": "json_object"},
                        temperature=0
                    )
                    extracted_json = json.loads(response.choices[0].message.content)
                    print("  [OK] English Extraction successful via Groq")
                    break
            except Exception as e:
                print(f"  [Error] Attempt {attempt} failed: {e}", flush=True)
                time.sleep(5)
                attempt += 1
        
        if not extracted_json or not isinstance(extracted_json, dict):
            print("  [CRITICAL] AI returned invalid JSON structure (not a dict). Creating dummy object.")
            extracted_json = {
                "brief_summary": "Summary unavailable.",
                "summary": f"[AI Summary Failed. Raw Text:]\n\n{chunk_text}", 
                "characters": [], 
                "locations": [], 
                "glossary": []
            }
            
        print(f"  -> Processing {part_title} (Sanskrit Agent)...", flush=True)
        
        if extracted_json.get("brief_summary") == "Summary unavailable.":
            print("  [Warning] Skipping Sanskrit extraction because English summary failed.", flush=True)
            extracted_json["sanskrit_insight"] = None
        else:
            prompt_2 = f'''You are a Sanskrit linguistic expert. 
            I am giving you a brief summary of what happens in this specific part of the Mahabharata.
            I am also giving you the raw authentic Sanskrit text scraped directly from the source.
            Your job is to search the text and extract an original Sanskrit verse (sloka) that SPECIFICALLY MATCHES the events in this summary.
            - CRITICAL RULE: You must NOT use any of these previously used verses: {json.dumps(used_sanskrit_verses, ensure_ascii=False)}
            Required JSON Schema:
            {{
                "sanskrit_insight": {{"fact": "Mind-blowing insight about the sanskrit words used in this specific verse", "sanskrit_verse": "Original sanskrit sloka", "translation": "English translation"}}
            }}
            Brief Summary of this part: "{extracted_json.get('brief_summary', '')}"
            Raw Sanskrit Text to search through: {raw_sanskrit_html_text[:10000]}'''
            
            sanskrit_attempt = 0
            while sanskrit_attempt < 3:
                try:
                    response = groq_client.chat.completions.create(
                        model="openai/gpt-oss-120b",
                        messages=[{"role": "user", "content": prompt_2}],
                        response_format={"type": "json_object"},
                        temperature=0
                    )
                    sanskrit_json = json.loads(response.choices[0].message.content)
                    extracted_json["sanskrit_insight"] = sanskrit_json.get("sanskrit_insight")
                    print("  [OK] Sanskrit Extraction successful via Groq")
                    break
                except Exception as e:
                    print(f"  [Error] Sanskrit Attempt {sanskrit_attempt} failed: {e}", flush=True)
                    time.sleep(5)
                    sanskrit_attempt += 1
            
        part_section_data = {
            "global_id": part_global_id,
            "title": part_title,
            "url": current_url
        }
        
        # Add verse to memory so it's not repeated
        if extracted_json.get("sanskrit_insight") and extracted_json["sanskrit_insight"].get("sanskrit_verse"):
            used_sanskrit_verses.append(extracted_json["sanskrit_insight"]["sanskrit_verse"])
        
        push_to_neo4j(book_title, parva_title, part_section_data, extracted_json)
        print(f"  [OK] Successfully extracted and pushed {part_title} to Neo4j!", flush=True)
                
        time.sleep(5)
        
        # Stop after Part 2 as requested
        if part_idx == 1:
            print("Stopping after Part 2 as requested for testing.", flush=True)
            break
        
    global_section_id += 1
    
    if next_rel_link and global_section_id == 2:
        print("Stopping after Section 1 as requested for testing. Finished.")
        break
    elif next_rel_link:
        current_url = urljoin(current_url, next_rel_link)
    else:
        print("No next link found. Finished.")
        break

db_driver.close()
