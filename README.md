# Fashion Trend Intelligence — Python Backend

A FastAPI backend that scores fashion trend momentum using runway show data,
Google Trends search signals, and (optionally) social media velocity.

## Architecture

```
fashion-backend/
├── app/
│   ├── main.py               # FastAPI app + CORS + startup
│   ├── config.py             # Settings from .env
│   ├── db/
│   │   └── session.py        # Async SQLAlchemy engine + session
│   ├── models/
│   │   └── database.py       # ORM: Show, Look, TrendItem, TrendScore, SearchSignal
│   ├── routers/
│   │   └── trends.py         # REST endpoints
│   └── services/
│       ├── trend_scorer.py   # ⭐ Core scoring engine
│       ├── ingestion.py      # Tagwalk API + Google Vision tagging
│       ├── search_trends.py  # pytrends / Google Trends ingestion
│       └── scheduler.py      # Celery beat daily/weekly jobs
└── tests/
    └── test_scorer.py        # Unit tests for scoring logic
```

## Trend Scoring Formula

```
composite_score = w_runway * runway_score
                + w_search * search_score
                + w_social * social_score
```

**Default weights (configurable in .env):**
| Signal         | Weight | Source                            |
|----------------|--------|-----------------------------------|
| Runway         | 50%    | Tagwalk API look counts           |
| Search         | 30%    | Google Trends (via pytrends)      |
| Social         | 20%    | Instagram/TikTok hashtag velocity |

Each sub-score is normalised to 0–100 before weighting.
A daily delta (% change) flags items as **rising** if Δ > 5%.

---

## Quick Start

### 1. Clone & install

```bash
cd fashion-backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env — add your API keys and DB URL
```

For local dev with no Postgres, the default SQLite URL works fine:
```
DATABASE_URL=sqlite+aiosqlite:///./fashion_trends.db
```

### 3. Run the API

```bash
uvicorn app.main:app --reload --port 8000
```

Visit **http://localhost:8000/docs** for the interactive Swagger UI.

### 4. Seed data (first run)

```bash
# Ingest runway shows from Tagwalk
curl -X POST "http://localhost:8000/api/trends/ingest/runway?season=FW26"

# Pull Google Trends for seed keywords
curl -X POST "http://localhost:8000/api/trends/ingest/search?season=FW26"

# Run scoring pipeline
curl -X POST "http://localhost:8000/api/trends/run-scoring?season=FW26"
```

---

## API Endpoints

| Method | Path                          | Description                        |
|--------|-------------------------------|------------------------------------|
| GET    | `/api/trends`                 | Top trending items (sorted by score)|
| GET    | `/api/trends/keywords`        | Keyword tag cloud data              |
| GET    | `/api/trends/materials`       | Materials bar chart data            |
| GET    | `/api/trends/colors`          | Seasonal color palette              |
| GET    | `/api/trends/{id}/history`    | Time-series scores for charts       |
| GET    | `/api/trends/shows`           | Indexed shows list                  |
| POST   | `/api/trends/run-scoring`     | Trigger scoring pipeline            |
| POST   | `/api/trends/ingest/runway`   | Trigger Tagwalk ingestion           |
| POST   | `/api/trends/ingest/search`   | Trigger Google Trends ingestion     |

---

## Automated Jobs (Celery)

Start Redis, then:

```bash
# Worker
celery -A app.services.scheduler worker --loglevel=info

# Beat scheduler (cron)
celery -A app.services.scheduler beat --loglevel=info
```

**Schedule:**
- **Daily 6 AM UTC** — pull Google Trends for all tracked keywords
- **Daily 7 AM UTC** — recompute all trend scores
- **Weekly Monday 4 AM UTC** — re-index runway shows from Tagwalk

---

## API Keys You'll Need

| Service              | Where to get it                          | Used for                    |
|----------------------|------------------------------------------|-----------------------------|
| **Tagwalk API**      | https://tagwalk.com/api (contact them)   | Runway look data            |
| **Google Vision**    | https://console.cloud.google.com         | Image → material/color tags |
| **Google Trends**    | Free via pytrends (no key needed)        | Search volume signals       |
| **Instagram Graph**  | https://developers.facebook.com          | Social hashtag velocity     |

> **Note:** pytrends doesn't require an API key — it scrapes Google Trends.
> For production volume, consider purchasing a data provider like
> **Trendalytics**, **EDITED**, or **WGSN** for structured fashion data.

---

## Connecting to the Frontend

In your `fashion-trends.html`, replace the hardcoded data arrays with `fetch()` calls:

```javascript
// Replace hardcoded keywords with live data
const resp = await fetch("http://localhost:8000/api/trends/keywords?season=FW26");
const keywords = await resp.json();
// keywords = [{ name, score, delta, category, is_rising }, ...]

// Time-series for the chart
const histResp = await fetch("http://localhost:8000/api/trends/1/history?days=90");
const history = await histResp.json();
// history = [{ date, composite, runway_score, search_score, social_score }, ...]
```

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Deployment

Recommended stack:
- **Render.com** — free tier for FastAPI + Postgres
- **Railway** — easy Redis + Postgres + Python deployment
- **Fly.io** — good for the Celery worker + beat scheduler

Set all `.env` variables as environment variables in your hosting dashboard.
