import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from neo4j import GraphDatabase
from groq import Groq
import json
from dotenv import load_dotenv
import threading
import uuid
import universal_ingestion
import centroid_classifier

load_dotenv(dotenv_path="../.env")

app = Flask(__name__)
CORS(app)

URI = os.getenv("NEO4J_URI", "neo4j+s://p-mt-2e58c6e6c448-11-0110.production-orch-0703.neo4j.io")
USER = os.getenv("NEO4J_USERNAME", "neo4j")
PWD = os.getenv("NEO4J_PASSWORD", "BvWcQ_00z90E76Q-C1FvQzO7q38BpxJp9c8_7T0q1tI")

driver = GraphDatabase.driver(URI, auth=(USER, PWD))
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

JOBS = {}

SCHEMA_CONTEXT = """
Neo4j Graph Schema:
- (b:Book)-[:CONTAINS]->(p:Parva)-[:CONTAINS]->(s:Section)
- (s:Section)-[:MENTIONS_CHARACTER {context: string}]->(c:Character {name: string})
- (s:Section)-[:MENTIONS_LOCATION {context: string}]->(l:Location {name: string})
- (s:Section)-[:MENTIONS_TERM]->(g:GlossaryTerm {term: string, definition_indian: string})
- (s:Section)-[:HAS_LORE]->(f:Fact {topic: string, content: string})
- s:Section has properties: global_id, title, summary, brief_summary
"""

@app.route('/api/ask', methods=['POST'])
def ask_agent():
    data = request.json
    user_query = data.get('query', '')
    
    if not user_query:
        return jsonify({"answer": "Please ask a question."})

    cypher_prompt = f"""You are a Neo4j Cypher expert. Given the following schema:
{SCHEMA_CONTEXT}
Write a Cypher query to answer the user's question. 
Return ONLY the RAW CYPHER QUERY string. No markdown formatting, no explanation.
Ensure you use case-insensitive matching where appropriate (e.g. toLower(c.name) CONTAINS toLower('vyasa')).
User Question: {user_query}
"""
    
    try:
        completion = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role": "user", "content": cypher_prompt}],
            temperature=0,
            max_tokens=200
        )
        
        cypher_query = completion.choices[0].message.content.strip()
        cypher_query = cypher_query.replace('```cypher', '').replace('```', '').strip()
        
        print(f"Generated Cypher:\n{cypher_query}", flush=True)
        
        with driver.session() as session:
            result = session.run(cypher_query)
            records = [dict(record) for record in result]
            
        print(f"DB Results: {len(records)} records found.", flush=True)
        
        answer_prompt = f"""You are the Mahabharata GraphRAG Agent. 
A user asked: "{user_query}"
I queried the Neo4j database and found this data:
{json.dumps(records, default=str)[:3000]}

Write a highly engaging, concise, and insightful answer based ONLY on the provided database results.
If the database results are empty, tell the user you don't have that information in your knowledge graph yet.
"""
        
        final_completion = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role": "system", "content": "You are a helpful GraphRAG assistant."}, {"role": "user", "content": answer_prompt}],
            temperature=0.7,
            max_tokens=500
        )
        
        final_answer = final_completion.choices[0].message.content.strip()
        return jsonify({"answer": final_answer, "cypher": cypher_query})

    except Exception as e:
        print(f"Error: {e}", flush=True)
        return jsonify({"answer": f"Sorry, my neural link to Neo4j was disrupted. Error: {str(e)}"})


def process_upload_job(job_id, target, is_url):
    try:
        JOBS[job_id] = {"status": "processing", "message": "Downloading and parsing text...", "progress": 10}
        
        draft_chunks = universal_ingestion.ingest_file(target, is_url)
        if not draft_chunks:
            JOBS[job_id] = {"status": "error", "message": "Failed to extract or parse text."}
            return
            
        # Ensure it's a list
        if isinstance(draft_chunks, dict):
            draft_chunks = [draft_chunks]
            
        final_drafts = []
        
        for i, chunk_data in enumerate(draft_chunks):
            JOBS[job_id]["message"] = f"Classifying Part {i+1} of {len(draft_chunks)}..."
            JOBS[job_id]["progress"] = 10 + int((i / len(draft_chunks)) * 80)
            
            # Phase 3: Dynamic LLM Storyline Classification for each chunk
            classification_prompt = f"""
            Analyze this mythological event and classify it.
            Raw Extracted Text: {chunk_data.get('raw_text_snippet', chunk_data.get('summary', ''))}
            
            CRITICAL INSTRUCTIONS:
            1. Ignore any Sanskrit, Hindi, or non-English script. Only extract meaning from the English text.
            2. Read carefully to identify the EXACT Book and Parva/Kaanda (e.g., if the text says 'Baala Kaanda', do not classify it as 'Ayodhya Kanda').
            
            Output a strict JSON object with:
            - "book_title": The grand storyline or epic this belongs to (e.g. "The Ramayana", "The Legends of Ganesha").
            - "parva_title": The specific chapter or arc (e.g. "Baala Kaanda").
            - "epoch_order": An integer from 1 to 100 where 1 is the beginning of time.
            - "better_summary": A beautifully written, engaging 3-sentence summary in pure English based on the raw text.
            - "glossary": An array of objects {{ "term": "...", "definition_indian": "..." }} for complex terms/philosophies.
            - "lore": An array of objects {{ "topic": "...", "content": "..." }} for cool facts/lore from the text.
            """
            try:
                completion = client.chat.completions.create(
                    model="openai/gpt-oss-120b",
                    messages=[{"role": "user", "content": classification_prompt}],
                    response_format={"type": "json_object"},
                    temperature=0.2
                )
                dyn_class = json.loads(completion.choices[0].message.content)
                chunk_data['dynamic_classification'] = dyn_class
                if 'better_summary' in dyn_class:
                    chunk_data['summary'] = dyn_class['better_summary']
            except Exception as e:
                print("Dynamic classification failed:", e)
                chunk_data['dynamic_classification'] = {
                    "book_title": "Expanded Universe (User Uploads)",
                    "parva_title": "Unknown Arc",
                    "epoch_order": 99
                }
            
            final_drafts.append(chunk_data)
            
        JOBS[job_id] = {"status": "complete", "message": "Done", "progress": 100, "result": final_drafts}
        
    except Exception as e:
        print(f"Job Error: {e}", flush=True)
        JOBS[job_id] = {"status": "error", "message": str(e)}

@app.route('/api/upload', methods=['POST'])
def handle_upload():
    data = request.json
    target = data.get('target', '').strip()
    if not target:
        return jsonify({"error": "No target provided."})
        
    is_url = target.startswith('http')
    
    # URL Deduplication Check
    if is_url:
        with driver.session() as session:
            res = session.run("MATCH (s:Section {url: $url}) RETURN s.title AS title LIMIT 1", url=target)
            record = res.single()
            if record:
                return jsonify({"already_exists": True, "title": record["title"]})
                
    job_id = str(uuid.uuid4())
    JOBS[job_id] = {"status": "starting", "message": "Initializing...", "progress": 0}
    
    thread = threading.Thread(target=process_upload_job, args=(job_id, target, is_url))
    thread.start()
    
    return jsonify({"job_id": job_id})

@app.route('/api/status/<job_id>', methods=['GET'])
def check_status(job_id):
    if job_id not in JOBS:
        return jsonify({"status": "error", "message": "Job not found"})
    return jsonify(JOBS[job_id])

@app.route('/api/approve', methods=['POST'])
def handle_approve():
    data = request.json
    # Ensure we handle array of drafts
    drafts = data if isinstance(data, list) else [data]
    
    try:
        with driver.session() as session:
            prev_id = None
            for idx, draft in enumerate(drafts):
                query = """
                MERGE (b:Book {title: $book_title})
                ON CREATE SET b.epoch_order = $epoch_order
                ON MATCH SET b.epoch_order = CASE WHEN b.epoch_order IS NULL THEN $epoch_order ELSE b.epoch_order END
                MERGE (p:Parva {title: $parva_title})
                MERGE (b)-[:CONTAINS]->(p)
                CREATE (s:Section {
                    global_id: $gid, 
                    title: $title, 
                    summary: $summary,
                    url: $url
                })
                MERGE (p)-[:CONTAINS]->(s)
                """
                
                import uuid as uuid_mod
                import time
                # Generate a sequential ID so Neo4j ORDER BY global_id ASC works properly
                new_id = f"EXT_{int(time.time())}_{idx:03d}_{str(uuid_mod.uuid4())[:4]}"
                
                dyn = draft.get('dynamic_classification', {})
                book_title = dyn.get('book_title', "Expanded Universe (User Uploads)")
                parva_title = dyn.get('parva_title', "Unknown Arc")
                epoch_order = dyn.get('epoch_order', 99)
                
                title_suffix = f" (Part {draft.get('part_number', 1)})" if draft.get('total_parts', 1) > 1 else ""
                
                session.run(query, 
                    book_title=book_title,
                    parva_title=parva_title,
                    epoch_order=epoch_order,
                    gid=new_id,
                    title="User Upload: " + parva_title + title_suffix,
                    summary=draft['summary'],
                    url=draft.get('source_url', '')
                )
                
                # Link sequential parts
                if prev_id:
                    session.run("MATCH (s1:Section {global_id: $prev}), (s2:Section {global_id: $curr}) MERGE (s1)-[:NEXT_PART]->(s2)", prev=prev_id, curr=new_id)
                prev_id = new_id
                
                for char in draft.get('characters', []):
                    session.run("MATCH (s:Section {global_id: $sid}) MERGE (c:Character {name: $cname}) MERGE (s)-[:MENTIONS_CHARACTER]->(c)", sid=new_id, cname=char['name'])
                    
                for term in dyn.get('glossary', []):
                    if isinstance(term, dict) and 'term' in term:
                        session.run("MATCH (s:Section {global_id: $sid}) MERGE (g:GlossaryTerm {term: $term}) ON CREATE SET g.definition_indian = $definition MERGE (s)-[:MENTIONS_TERM]->(g)", sid=new_id, term=term['term'], definition=term.get('definition_indian', ''))

                for fact in dyn.get('lore', []):
                    if isinstance(fact, dict) and 'topic' in fact:
                        session.run("MATCH (s:Section {global_id: $sid}) MERGE (f:Fact {topic: $topic}) ON CREATE SET f.content = $content MERGE (s)-[:HAS_LORE]->(f)", sid=new_id, topic=fact['topic'], content=fact.get('content', ''))

            return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    app.run(port=5000, debug=True, use_reloader=False)
