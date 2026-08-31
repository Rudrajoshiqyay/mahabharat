# Architecture: Mahabharata GraphRAG

## Core Problem
Standard Vector RAG suffers from "Timeline Hallucination" when querying massive chronological epics like the Mahabharata (e.g., confusing battles that happen in Book 4 with Book 7).

## The "Ultra Best" Solution
We enforce strict linear time using a Graph Database. Every section of the epic is assigned a sequential `global_id`. All characters and locations are explicitly connected to these chronological event nodes. Furthermore, we semantically match real Sanskrit verses to the corresponding English timelines.

## Technology Stack
- **Web Scraper:** Apify (`apify/cheerio-scraper`) for stealthy, reliable HTML extraction from Wisdomlib.
- **English Parser:** Groq (`openai/gpt-oss-20b`) to quickly convert raw English text into strict JSON structured metadata (Characters, Locations, Summary).
- **Sanskrit Semantic Matcher:** Google Gemini (`gemini-3.6-flash`) for deep semantic translation and matching of original Sanskrit verses to English summaries.
- **Database:** Neo4j AuraDB (Free Cloud) for Graph storage and Cypher relationship mapping.
- **Frontend Canvas:** React, Vite, Tailwind CSS, and `react-force-graph-2d` for interactive web visualization.

## The Data Pipeline
1. `parse_index.py`: Extracts the table of contents and assigns a strict `global_id` to each chapter, saving to `book1_queue.json`.
2. `unified_pipeline.py`: 
   - A synchronous pipeline that safely scrapes URLs using Apify.
   - Generates English Summaries using Groq.
   - Pushes Nodes (`:Book`, `:Parva`, `:Section`, `:Character`, `:Location`) directly into Neo4j.
   - Immediately invokes Gemini to semantically match raw Sanskrit verses to the English Summary.
   - Implements a strict state machine (`pipeline_state.json`) that halts the crawler entirely if a Sanskrit match fails, ensuring data integrity.
   - Uses exponential backoff (retries on 503 errors) to respect Gemini API limits.
