# Review Signal

An operator tool for running paid customer-review audits. You load a client's reviews,
it reads every one of them, merges what people said into a ranked work list, and prints
a report you hand back.

The number the report is built around is **star cost**: the difference in average rating
between reviews that mention a theme and reviews that don't. Frequency alone says
"lots of people mention portion size". Star cost says "portion size costs you 0.47 stars,
online order errors cost you 2.0 — fix the second one first."

## What it does

1. **Ingest** — CSV, XLSX or JSON export, or pasted text. Column names are auto-detected
   across the shapes Google Takeout, Judge.me, Loox, Yotpo and Trustpilot exports arrive in.
   Duplicates are fingerprinted out.
2. **Extract** — every review is read once and its topics pulled out with sentiment,
   severity 1–5, and a verbatim supporting excerpt.
3. **Consolidate** — a second pass merges near-duplicate labels ("slow service",
   "waited 40 minutes", "long wait") into canonical themes. Without this pass the
   frequency counts are meaningless, which is why most competing tools output word clouds.
4. **Score** — share of reviews, average severity, star cost, month-by-month trend,
   and a combined priority.
5. **Report** — ranked work list, praise list, volume/rating timeline, optional written
   summary. Print to PDF from the browser.

## Running it

Backend:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # add your ANTHROPIC_API_KEY
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev                 # http://localhost:5173
```

Vite proxies `/api` to port 8000, so no CORS setup is needed in development.

Try it with `sample_reviews.csv` in the repo root: create a project, set the business
type to "independent restaurant", upload the file, run the analysis.

## Cost per audit

Roughly 500–900 input tokens per review through the extraction pass, plus one
consolidation call. A 300-review audit runs a few cents to low single-digit dollars
depending on the model. Set `ANTHROPIC_MODEL` in `.env`; Haiku is enough for extraction
on short reviews, Sonnet is noticeably better at severity and at the consolidation pass.

## Getting the reviews in the first place

There is no legal bulk API for Google or Yelp reviews of businesses you don't own.
Google's Business Profile API only covers locations the account manages, and Yelp's
public API returns a few excerpts per business. The workable routes, in order:

- The client exports their own reviews (Shopify review apps, Trustpilot, Yotpo all export CSV).
- The client adds you as a manager on their Google Business Profile and you export.
- Small corpora: copy-paste into the paste box.

Build the OAuth flow for Google Business Profile only after clients ask for recurring
monthly reports. Until then manual export costs you ten minutes per client and zero
approval risk.

## Where this goes next

The pieces a paying customer will ask for, in the order they usually ask:

- Comparison against a competitor's review corpus in the same category.
- Recurring monthly runs with a diff against last month.
- Reply drafting for unanswered negative reviews.
- Per-location breakdown for multi-site businesses.

None of them are worth building before someone has paid for the one-off report.
