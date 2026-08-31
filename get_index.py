import os
from dotenv import load_dotenv
from apify_client import ApifyClient

load_dotenv()
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN")

print("Authenticating with Apify...")
client = ApifyClient(APIFY_API_TOKEN)

run_input = {
    "startUrls": [{"url": "https://www.wisdomlib.org/hinduism/book/the-mahabharata-mohan"}],
    "pageFunction": "async function pageFunction(context) { const $ = context.$; return { html: $('body').html() }; }"
}

print("Triggering Apify Cloud Scraper (apify/cheerio-scraper)...")
run = client.actor("apify/cheerio-scraper").call(run_input=run_input)

print("Scrape complete! Downloading data...")

# Handle Apify Client v3 Pydantic 'Run' objects
dataset_id = getattr(run, 'default_dataset_id', getattr(run, 'defaultDatasetId', None))
if dataset_id is None:
    # Fallback to model_dump if it's a strict Pydantic model
    dataset_id = run.model_dump().get("defaultDatasetId", run.model_dump().get("default_dataset_id"))

dataset_client = client.dataset(dataset_id)
for item in dataset_client.iterate_items():
    with open("index_raw.html", "w", encoding="utf-8") as f:
        f.write(item.get("html", ""))
    print("SUCCESS: Saved the raw website data to index_raw.html!")
    break
