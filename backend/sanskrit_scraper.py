import requests
import re
from bs4 import BeautifulSoup

def get_sanskrit_verses(book_num, part_num):
    """
    Scrapes sanskritsahitya.org for the exact sanskrit verses of a given section.
    Args:
        book_num: integer (e.g. 1)
        part_num: integer (e.g. 1)
    Returns:
        String containing the first 10,000 characters of pure Sanskrit verses.
    """
    url = f"https://sanskritsahitya.org/mahabharatam/{book_num}.{part_num}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Upgrade-Insecure-Requests': '1'
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"Failed to fetch Sanskrit for {book_num}.{part_num}: {e}")
        return ""

    soup = BeautifulSoup(response.text, 'html.parser')
    text = soup.get_text(separator='\n', strip=True)
    
    # Filter out navigation headers/menus by only keeping lines with Devanagari characters
    devanagari_lines = [line for line in text.split('\n') if re.search(r'[\u0900-\u097F]', line)]
    
    return "\n".join(devanagari_lines)[:10000]

if __name__ == "__main__":
    # Test block
    text = get_sanskrit_verses(1, 1)
    print(f"Extracted {len(text)} characters of Sanskrit.")
