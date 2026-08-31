import requests
from bs4 import BeautifulSoup

url = "https://www.wisdomlib.org/hinduism/book/the-mahabharata-mohan/d/doc374926.html"
res = requests.get(url)
soup = BeautifulSoup(res.text, 'html.parser')

print(soup.prettify()[10000:15000])
