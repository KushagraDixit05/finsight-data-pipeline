# FinSight AI — News Data Collection & Storage Pipeline

A production-grade, phase-wise news data pipeline that fetches, normalizes, deduplicates, stores, and embeds financial news articles for the FinSight AI portfolio intelligence platform.

## What this pipeline does

```
Cron (every 2h) → Adapters (4 providers) → Normalize → Validate → Deduplicate → PostgreSQL
                                                                                     ↓
                                                                            Embedding Job
                                                                                     ↓
                                                                           pgvector (news_article_embeddings)
```

**Scope**: Clean, deduplicated, queryable, embeddable news articles. This pipeline does **not** do portfolio impact analysis, LLM reasoning, or frontend work.

## Project structure

```
src/news/
├── config.py                  # Central env var configuration
├── models/
│   ├── enums.py               # NewsCategory (7), NewsSource (4)
│   └── news_article.py        # Canonical NewsArticle Pydantic model
├── adapters/
│   ├── base.py                # Shared exceptions + ProviderConfig
│   ├── finnhub.py             # Finnhub adapter
│   ├── marketaux.py           # Marketaux adapter
│   ├── newsdata.py            # NewsData.io adapter
│   └── gdelt.py               # GDELT adapter (metadata-only)
├── collectors/
│   └── news_collector.py      # Orchestrates all 4 adapters
├── normalizers/
│   ├── text.py                # HTML stripping, whitespace
│   ├── datetime_utils.py      # UTC parsing for all provider formats
│   ├── url.py                 # Canonical URL normalization + tracking param removal
│   ├── geo.py                 # ISO 3166-1 / ISO 639-1 validation
│   ├── pipeline.py            # Main normalize() function (11 rules)
│   └── validate.py            # ValidationResult + validate()
├── deduplication/
│   └── check.py               # 3-level duplicate detection
├── database/
│   ├── session.py             # SQLAlchemy engine + session factory
│   ├── models.py              # ORM models (7 tables)
│   └── repository.py          # insert_article, log_ingestion_run, etc.
├── scheduler/
│   ├── lock.py                # PostgreSQL advisory lock
│   ├── window.py              # Overlap-window fetch window computation
│   └── run_ingestion.py       # Cron entry point
└── embeddings/
    ├── models.py              # NewsArticleEmbedding ORM model (pgvector)
    └── generate.py            # Batch embedding generation + storage
migrations/
├── env.py                     # Alembic environment (reads DATABASE_URL)
└── versions/
    ├── 001_create_news_sources.py
    ├── 002_create_news_categories.py
    ├── 003_create_news_articles.py
    ├── 004_create_entity_topic_tables.py
    ├── 005_create_news_ingestion_logs.py
    └── 006_create_news_article_embeddings.py
tests/
├── conftest.py
├── fixtures/                  # Recorded provider responses (no live API calls in tests)
├── test_adapters.py
├── test_normalization.py
├── test_validation.py
├── test_deduplication.py
├── test_database.py
└── test_scheduler.py
```

## Quickstart

### 1. Install dependencies

```bash
pip install -e ".[dev]"
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your API keys and DATABASE_URL
```

### 3. Run database migrations

```bash
alembic upgrade head
```

### 4. Run the ingestion job manually

```bash
python -m src.news.scheduler.run_ingestion
```

### 5. Run tests

```bash
pytest
# For database-level tests, set TEST_DATABASE_URL first:
TEST_DATABASE_URL=postgresql://... pytest tests/test_database.py
```

## Cron schedule

```cron
0 */2 * * * cd /app && /app/.venv/bin/python -m src.news.scheduler.run_ingestion >> /var/log/finsight/news_ingestion.log 2>&1
```

## Design decisions pending

See [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md) for decisions that must be made before production deployment.

## Development plan

See [`development plan/`](development%20plan/) for the full phase-by-phase specification.
