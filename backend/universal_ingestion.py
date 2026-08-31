import os
import sys
import json
import PyPDF2
from playwright.sync_api import sync_playwright
import spacy
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8')

# Load the local NLP model (Zero API/LLM calls)
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    print("Downloading local NLP model...")
    os.system(f"{sys.executable} -m spacy download en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")

def extract_text_from_pdf(pdf_path):
    print(f"Extracting text from PDF: {pdf_path}")
    text = ""
    try:
        with open(pdf_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        print(f"Error reading PDF: {e}")
    return text

def extract_text_from_url(url):
    print(f"Extracting text via Playwright: {url}")
    text = ""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=30000)
            # Extract only paragraph texts to avoid navbars/footers
            paragraphs = page.locator("p").all_inner_texts()
            if paragraphs:
                text = "\\n\\n".join([p.strip() for p in paragraphs if len(p.strip()) > 20])
            
            if not text:
                text = page.locator("body").inner_text()
                
            browser.close()
    except Exception as e:
        print(f"Error reading URL: {e}")
    return text

def summarize_locally(text, num_sentences=4):
    """Extractive summary using basic word frequency math (Zero LLM)"""
    doc = nlp(text)
    words = [token.text.lower() for token in doc if not token.is_stop and not token.is_punct]
    word_freq = Counter(words)
    
    if not word_freq:
        return text[:500]
        
    max_freq = max(word_freq.values())
    for word in word_freq.keys():
        word_freq[word] = (word_freq[word] / max_freq)
        
    sentence_scores = {}
    for sent in doc.sents:
        for word in sent:
            if word.text.lower() in word_freq:
                if len(sent.text.split(' ')) < 30: # Penalize extremely long sentences
                    sentence_scores[sent] = sentence_scores.get(sent, 0) + word_freq[word.text.lower()]
                    
    import heapq
    summarized_sents = heapq.nlargest(num_sentences, sentence_scores, key=sentence_scores.get)
    return " ".join([sent.text.replace('\n', ' ').strip() for sent in summarized_sents])

def parse_with_nlp(raw_text):
    print("Running Local NLP extraction (Zero LLM Tokens)...")
    # Truncate text for performance on local CPU
    text_to_process = raw_text[:50000] 
    
    doc = nlp(text_to_process)
    
    characters = set()
    locations = set()
    
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            characters.add(ent.text.replace('\n', ' ').strip())
        elif ent.label_ in ["GPE", "LOC", "FAC"]:
            locations.add(ent.text.replace('\n', ' ').strip())
            
    # Generate local summary using math
    summary = summarize_locally(text_to_process)
    
    return {
        "summary": summary,
        "raw_text_snippet": text_to_process[:3000],
        "characters": [{"name": c, "context": "Extracted locally without LLM"} for c in list(characters)[:10] if len(c)>2],
        "locations": [{"name": l, "context": "Extracted locally without LLM"} for l in list(locations)[:10] if len(l)>2],
        "mind_blowing_lore": [] # Lore generation requires generative AI, skipping for token preservation
    }

def ingest_file(input_path, is_url=False):
    if is_url:
        raw_text = extract_text_from_url(input_path)
    elif input_path.endswith('.pdf'):
        raw_text = extract_text_from_pdf(input_path)
    else:
        with open(input_path, 'r', encoding='utf-8') as f:
            raw_text = f.read()

    if not raw_text.strip():
        print("No text could be extracted.")
        return None

    print(f"Extracted {len(raw_text)} characters of raw text.")
    
    chunks = []
    current_chunk = ""
    # Split by double newline or single newline
    paragraphs = raw_text.split('\n')
    for p in paragraphs:
        if len(current_chunk) + len(p) > 8000:
            if current_chunk.strip():
                chunks.append(current_chunk)
            current_chunk = p + "\n"
        else:
            current_chunk += p + "\n"
    if current_chunk.strip():
        chunks.append(current_chunk)
        
    extracted_chunks = []
    for i, chunk in enumerate(chunks):
        print(f"Processing chunk {i+1}/{len(chunks)}...")
        data = parse_with_nlp(chunk)
        if is_url:
            data["source_url"] = input_path
        data["part_number"] = i + 1
        data["total_parts"] = len(chunks)
        extracted_chunks.append(data)
        
    if extracted_chunks:
        draft_path = "draft_upload.json"
        with open(draft_path, "w", encoding="utf-8") as f:
            json.dump(extracted_chunks, f, indent=4)
        print(f"Draft extraction saved to {draft_path}")
        
    return extracted_chunks

if __name__ == "__main__":
    if len(sys.argv) > 1:
        target = sys.argv[1]
        is_url = target.startswith('http')
        ingest_file(target, is_url)
    else:
        print("Usage: python universal_ingestion.py <file.pdf | url | file.txt>")
