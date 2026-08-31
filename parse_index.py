import json
from bs4 import BeautifulSoup

print("Opening raw HTML file...")
try:
    with open("index_raw.html", "r", encoding="utf-8") as f:
        html = f.read()
except FileNotFoundError:
    print("ERROR: index_raw.html not found. Did the Apify scrape finish?")
    exit(1)

soup = BeautifulSoup(html, "html.parser")

base_url = "https://www.wisdomlib.org"
# We only want links that belong to the Mahabharata book
target_path = "/hinduism/book/the-mahabharata-mohan"

link_queue = []
timeline_id = 1

print("Extracting chronological links...")
# Find all link tags on the page
for a_tag in soup.find_all("a", href=True):
    href = a_tag["href"]
    text = a_tag.text.strip()
    
    # Filter: It must be a link inside the Mahabharata book, and not just a link to the main page itself
    if target_path in href and len(href) > len(target_path) + 1:
        # Construct the full URL if it is a relative link
        full_url = href if href.startswith("http") else base_url + href
        
        # Avoid putting the exact same URL in the queue twice
        if not any(item['url'] == full_url for item in link_queue):
            link_queue.append({
                "timeline_id": timeline_id,
                "title": text,
                "url": full_url
            })
            timeline_id += 1

print(f"Extracted {len(link_queue)} chronological chapters!")

# Save the master map
with open("link_queue.json", "w", encoding="utf-8") as f:
    json.dump(link_queue, f, indent=4)

print("SUCCESS: Saved chronological master map to link_queue.json")
