# Frugl

Grocery price comparison for Coles vs Woolworths. Type a weekly list (or scan a receipt), compare prices, and see which store is cheaper overall plus a per-item breakdown.

**Live app:** [https://open-home-loans-take-home-task.vercel.app/](https://open-home-loans-take-home-task.vercel.app/)

**Video:** [https://youtu.be/KdDWbSQ2k9Y](https://youtu.be/KdDWbSQ2k9Y)

Open Home Loans take-home assessment (Brief 3A).

## What it does

- **Build a list** manually and hit Compare
- **Scan a receipt** (Gemini OCR) → items go into the list so you can edit them → then Compare yourself
- **Results screen** with overall winner, savings, annualised savings, specials count, and per-item Woolworths vs Coles prices
- **Product links** when the API returns a URL ("View on Woolworths" / "View on Coles")
- Receipt compares use a **Groq reranker** so messy OCR lines match the right products more reliably than string matching alone

More detail on matching, specials detection, caching, etc. is in [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md).

## Stack

- **Frontend:** React + Vite + Tailwind (hosted on Vercel)
- **Backend:** FastAPI (Python), deployed separately (e.g. Render / Railway)
- **Prices:** Woolworths + Coles search via [RapidAPI](https://rapidapi.com/) (data-holdings-group)
- **Receipt OCR:** Google Gemini
- **Receipt product matching:** Groq (`llama-3.1-8b-instant`)

## Repo layout

```
backend/
  main.py              # FastAPI, CORS, rate limit, /health
  routers/             # /api/compare, /api/receipt
  services/            # store APIs, matching, compare, cache, rate limit
  tests/               # pytest
frontend/
  src/components/      # ListBuilder, Results, ReceiptUpload, etc.
  src/lib/api.js       # fetch helpers
```

## Run locally

### You need

- Python 3.11+
- Node 18+
- API keys (see below)

### Backend

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# fill in your keys in .env

uvicorn main:app --reload
```

Runs at `http://127.0.0.1:8000` (use this host on Windows; `localhost` can be weird with the Vite proxy).

- API docs: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/health`

**Receipt testing without the UI:** drop an image at `backend/tests/fixtures/test_receipt.jpg` and run `python scripts/test_receipt.py` from `backend/`. See [backend/docs/receipt_testing.md](backend/docs/receipt_testing.md). Swagger struggles with big base64 payloads so I usually test receipts that way.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

App at `http://localhost:5173`. By default Vite proxies `/api` to `http://127.0.0.1:8000`.

To point at a deployed backend instead:

```bash
# frontend/.env.local (not committed)
VITE_API_URL=https://your-backend-url-here
```

### Tests

```bash
cd backend
pytest
```

Right now that's **44 tests** (compare, matching, receipt parsing, cache, rate limit). They mock external APIs so you don't burn RapidAPI credits in CI.

GitHub Actions runs the same on push/PR (see `.github/workflows/backend-tests.yml`).

## Environment variables

Copy `backend/.env.example` to `backend/.env`. **Do not commit `.env`.**

| Variable | What it's for |
|----------|----------------|
| `RAPIDAPI_KEY` | Woolworths + Coles product search |
| `GEMINI_API_KEY` | Receipt image → item list |
| `GROQ_API_KEY` | Rerank store search results for receipt items |
| `SEARCH_CACHE_TTL_SECONDS` | Optional. Cache search results (default 900 = 15 min) |
| `RATE_LIMIT_PER_MINUTE` | Optional. Max `/api/*` requests per IP per minute (default 30) |
| `DEBUG_API_RESPONSES` | Optional. Set `true` to dump full RapidAPI JSON in logs |

On Vercel you only need **`VITE_API_URL`** set to your backend base URL (no trailing slash).

## Deployment (what I did)

- **Frontend:** Vercel, connected to this repo. Env: `VITE_API_URL` = backend URL.
- **Backend:** separate host with the env vars above. CORS in `main.py` allows the Vercel production URL and preview URLs.
- After changing backend env vars, **redeploy/restart** the backend or they won't apply.
- Optional: set your host's health check path to `/health`.

## If I had more time

- Broader brand list and better handling of edge-case product names (embeddings, more testing, etc.)
- Better API with more details (on special, out of stock, etc.)
- Loyalty points (Everyday Rewards / Flybuys) in the savings story
- Proper rate limiting behind a reverse proxy (real client IP)
- Frontend CI (lint/build) alongside backend tests

## License

Take-home assessment. Not meant as production-ready software without a proper review.
