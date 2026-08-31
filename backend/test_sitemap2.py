import requests
from bs4 import BeautifulSoup

url = "https://www.wisdomlib.org/hinduism/book/the-mahabharata-mohan/d/doc374926.html"
res = requests.get(url)
soup = BeautifulSoup(res.text, 'html.parser')

items = soup.find_all('a')
for a in items:
    if "Anukramanika" in a.text or "Section" in a.text:
        print(f"[{a.parent.name}] Class: {a.parent.get('class')} - Text: {a.text.strip()}, Link: {a.get('href')}")
