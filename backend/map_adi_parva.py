import requests
from bs4 import BeautifulSoup
import json
import re

url = "https://www.wisdomlib.org/hinduism/book/the-mahabharata-mohan/d/doc374926.html"
base_url = "https://www.wisdomlib.org"

print("Fetching Book 1 Index...")
res = requests.get(url)
soup = BeautifulSoup(res.text, 'html.parser')

# We need to find the main content div holding the tree.
# WisdomLib uses nested <ul> and <li> for the table of contents.
# Let's find all <a> tags that have href starting with /hinduism/book/the-mahabharata-mohan/d/
links = soup.find_all('a', href=re.compile(r'/hinduism/book/the-mahabharata-mohan/d/doc\d+\.html'))

book = {
    "title": "Book 1 - Adi Parva",
    "parvas": []
}

current_parva = None
section_counter = 1

for a in links:
    text = a.text.strip()
    href = a.get('href')
    if not href.startswith('http'):
        href = base_url + href
        
    if "Parva" in text and "Book 1" not in text:
        # This is a Parva node
        current_parva = {
            "title": text,
            "url": href,
            "sections": []
        }
        book["parvas"].append(current_parva)
    elif "Section" in text and current_parva is not None:
        # This is a Section belonging to the current Parva
        current_parva["sections"].append({
            "title": text,
            "url": href,
            "global_id": section_counter
        })
        section_counter += 1

print(f"Mapped {len(book['parvas'])} Parvas and {section_counter - 1} total Sections!")

with open("book1_queue.json", "w", encoding="utf-8") as f:
    json.dump(book, f, indent=2)
    
print("Saved to book1_queue.json")
