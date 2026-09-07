# 03 — Pipeline Architecture

## Objective

Define the component structure, folder layout, and data flow for the ingestion pipeline, and decide the scheduling mechanism.

## Why This Phase Exists

Before writing adapters or schema, the shape of the system must be fixed so every later phase builds into the right place instead of improvising structure per-phase.

## Prerequisites

`01-news-classification.md`, `02-api-selection.md` completed.

## Decisions

### Scheduler: cron + Python, not a job framework

- At 4 providers × 1 run / 2 hours = 12 runs/day, total API calls stay in the low hundreds/day. This does not need distributed task queues.
- **Decision: use OS-level `cron`** (or an equivalent — see note below) to invoke a single Python entrypoint script every 2 hours. The entrypoint does all orchestration in-process (call each adapter, normalize, dedupe, insert, log).
- Overlap prevention is handled with a **PostgreSQL advisory lock** taken at the start of the job and released at the end (or automatically on connection close) — this works correctly even if two cron ticks fire close together or a previous run is still finishing a slow API call. This is simpler and more portable than a separate lock file (which breaks across multiple hosts) and doesn't require Redis.
- If the deployment environment doesn't have a real crontab (e.g., a managed container platform), use that platform's scheduled-job feature (e.g., a Kubernetes CronJob, a cloud provider's scheduled function) to invoke the same entrypoint script — the script itself stays identical either way. Do not introduce Celery Beat, Airflow, or a custom scheduler daemon for this call volume.
- Python's own `APScheduler`/`schedule` libraries are **not used** either — an always-running Python process is more operationally fragile (needs its own supervisor/restart policy) than letting the OS/platform scheduler own scheduling and just invoking a script.

### Component responsibilities

```text
scheduler/     # cron entry, job lock, top-level orchestration
collectors/    # calls all adapters for a run, aggregates results
adapters/      # one file per provider: raw API JSON -> canonical NewsArticle
models/        # canonical NewsArticle dataclass/pydantic model + enums
normalizers/   # cleaning, text/date/category normalization (provider-agnostic)
deduplication/ # hashing + duplicate-check logic
database/      # SQLAlchemy models, session/connection handling, repository functions
embeddings/    # (phase 10) embedding generation + pgvector writes
config.py      # environment variable loading (single place)
```

Rationale for this split: adapters are the only code that knows about a specific provider's JSON shape (Rule 2 — API independence). Everything after `models/` operates purely on the canonical `NewsArticle` object and never imports a provider name.

### Data flow

```mermaid
flowchart TD
    A["cron: every 2 hours"] --> B["scheduler/run_ingestion.py"]
    B --> C{"Advisory lock free?"}
    C -->|No, already running| Z1["Log skip, exit 0"]
    C -->|Yes| D["collectors/news_collector.py"]

    D --> E1["adapters/marketaux.py"]
    D --> E2["adapters/finnhub.py"]
    D --> E3["adapters/newsdata.py"]
    D --> E4["adapters/gdelt.py"]

    E1 --> F["models.NewsArticle (canonical)"]
    E2 --> F
    E3 --> F
    E4 --> F

    F --> G["normalizers/pipeline.py: clean + normalize"]
    G --> H["normalizers/validate.py: required-field check"]
    H -->|invalid| Z2["Log + skip record"]
    H -->|valid| I["deduplication/check.py"]
    I -->|duplicate| Z3["Log + skip insert"]
    I -->|new| J["database/repository.py: insert"]

    J --> K[("PostgreSQL: news_articles")]
    B --> L[("PostgreSQL: news_ingestion_logs")]
    K -.->|async, separate job| M["embeddings/generate.py"]
    M --> N[("PostgreSQL: news_embeddings (pgvector)")]
```

### Fault isolation

Each adapter call is wrapped independently — one provider's failure (timeout, 429, malformed JSON, auth failure) is caught, logged to `news_ingestion_logs`, and does not stop the collector from processing the other 3 providers. Full behavior table in `12-end-to-end-integration.md`'s error-handling section and `09-ingestion-scheduler.md`.

### Embedding generation is decoupled

Embedding generation (phase 10) runs as a separate step **after** the insert transaction commits, either at the end of the same job run or as its own smaller, more frequent job. It must never block or roll back the ingestion of a news article — a failed embedding call means the row exists but is not yet searchable, which is an acceptable degraded state; a failed insert should never happen because embeddings were slow.

## Implementation Steps

```text
Step 1 — Create the top-level Python package structure under src/news/ with the folders listed above.
Step 2 — Add empty __init__.py files to make each folder a package.
Step 3 — Add config.py that reads all required environment variables at import time and fails fast with a clear error if any required variable is missing.
Step 4 — Confirm cron (or platform scheduler) is available in the target deployment environment; document the exact crontab line: `0 */2 * * * cd /app && /app/.venv/bin/python -m src.news.scheduler.run_ingestion >> /var/log/finsight/news_ingestion.log 2>&1`
Step 5 — Do not implement adapters/normalizers/database yet — those are separate phases. This phase only creates the skeleton and the scheduler shell that phase 09 will fill in.
```

## Files to Create/Modify

```text
src/news/
├── __init__.py
├── config.py
├── scheduler/
│   └── __init__.py
├── collectors/
│   └── __init__.py
├── adapters/
│   └── __init__.py
├── models/
│   └── __init__.py
├── normalizers/
│   └── __init__.py
├── deduplication/
│   └── __init__.py
├── database/
│   └── __init__.py
└── embeddings/
    └── __init__.py
```

## Database Changes

None in this phase.

## Configuration

```text
MARKETAUX_API_KEY=
FINNHUB_API_KEY=
NEWSDATA_API_KEY=
DATABASE_URL=postgresql://user:password@localhost:5432/finsight
NEWS_INGESTION_INTERVAL_HOURS=2
```

## Testing

None in this phase (skeleton only). Verify the package imports cleanly: `python -c "import src.news"`.

## Expected Result

An importable, empty package skeleton matching the architecture, plus a decided-and-documented scheduling mechanism (cron + advisory lock).

## Acceptance Criteria

```text
- [ ] Folder structure created exactly as specified
- [ ] config.py fails fast on missing required env vars
- [ ] Scheduler mechanism decided and documented: cron + PostgreSQL advisory lock, no Celery/Airflow/Kafka
- [ ] Crontab line documented
- [ ] Fault-isolation principle documented: one adapter failing must not stop others
```

## Dependencies / Next Phase

`04-canonical-data-model.md` defines the `NewsArticle` model that lives in `models/`.
