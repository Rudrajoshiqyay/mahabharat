# Project Rules

These rules dictate how code should be written and how the project should be managed.

## 1. Step-by-Step Approval (NEW)
- The AI must NEVER auto-approve or rush into executing a plan.
- Every architectural decision and code implementation must be explained.
- The AI must explain *why* a tool is being used, present the *alternatives*, and explain why the alternatives were rejected.
- Execution only happens after explicit user approval.

## 2. The Linearity Rule (Absolute Priority)
- The absolute most important aspect of this project is maintaining the chronological timeline of the Mahabharata.
- Every piece of scraped text MUST be attached to a sequentially incrementing `timeline_id`.

## 3. Advanced Web Scraping
- Approved core scraping tools: **Apify** and **Playwright/Selenium**.
- The crawler must be designed to bypass anti-bot systems efficiently.

## 4. Preserve Hierarchical Metadata
- Never just scrape the raw text. Always ensure the "Book", "Parent Parva", and Entities are captured.

## 5. Resilience & API Limits (NEW)
- The Mahabharata is massive. All Python code must include **Rate Limiting** (sleep timers) to never exceed Gemini's free tier limits.
- The scraper must use **Checkpointing**. It must save its progress after every single section so that if the API limit is reached, it can resume exactly where it left off the next day without starting over.
