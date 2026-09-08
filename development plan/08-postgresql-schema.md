# 08 — PostgreSQL Schema

## Objective

Design and create the PostgreSQL tables, constraints, and indexes that store normalized, deduplicated news, while keeping the schema extensible for future embeddings and knowledge-graph work without overbuilding either now.

## Why This Phase Exists

This is the persistent source of truth the rest of FinSight will eventually query. Getting constraints and indexes right here is what makes deduplication (`07-deduplication.md`) and idempotency (`09-ingestion-scheduler.md`) actually hold at the database level, not just in application code.

## Prerequisites

`04-canonical-data-model.md`, `07-deduplication.md` completed.

## Decisions

### Table-per-concept decisions

| Candidate table | Decision | Reasoning |
|---|---|---|
| `news_articles` | **Yes, core table** | The record itself |
| `news_sources` | **Yes, small lookup table** | Only 4 rows today, but needed to hold per-provider metadata (`license_type`, `stores_full_content`) that `02-api-selection.md` requires tracking — a plain string column couldn't carry that metadata |
| `news_categories` | **Yes, small lookup table** | 7 fixed rows; using a lookup table (rather than a DB `CHECK` enum) makes it trivial to add a `description` per category for future admin tooling, without a schema migration |
| `news_entities` | **Yes, but minimal** | Only `name`, `entity_type`, `ticker` — this is intentionally *not* the future knowledge graph; it exists so `tickers`/`companies` mentions can be queried relationally later without re-parsing JSONB, but no relationship/event modeling is added now (Rule 10) |
| `news_article_entities` | **Yes, junction table** | Many-to-many between articles and entities |
| `news_topics` / `news_article_topics` | **Yes, junction table** | Free-form tags; same pattern as entities |
| `news_ingestion_logs` | **Yes** | Required by Section 12 (error handling) and Section 17 (scheduler tests) — every job run must leave an auditable record |

### Normalization vs. denormalization

- **Denormalized on `news_articles`**: `tickers` (as `text[]`) and `companies` (as `jsonb`) are stored directly on the article row rather than fully normalized into `news_entities`/`news_article_entities` for *every* mention. Reasoning: for MVP, the primary read pattern is "find articles mentioning ticker X" (array-contains query, served well by a GIN index) and "show an article's raw provider-supplied entity list" (a display concern, well-served by JSONB). Fully normalizing every ticker mention into a junction table is unnecessary machinery for a read pattern this simple, and the entity tables still exist for the cases (named people/orgs, cross-article entity analytics) where a relational join actually adds value.
- **Normalized**: `source` and `category` are foreign keys into lookup tables, not free strings, so a typo can never silently create a new "category" that breaks the 7-value contract from `01-news-classification.md`.
- **Not built at all**: any table representing "events," "impact relationships," or "portfolio exposure" — explicitly deferred per Rule 10. The schema's extensibility comes from `news_articles.id` being a stable UUID any future table can reference, not from building those tables now.

### Constraints

- `news_articles.id`: `UUID PRIMARY KEY DEFAULT gen_random_uuid()` (requires the `pgcrypto` extension, or generate UUIDs in the application layer if the extension isn't available).
- `news_articles.source`: `NOT NULL`, `REFERENCES news_sources(id)`.
- `news_articles.category`: `NOT NULL`, `REFERENCES news_categories(id)`.
- `news_articles.url`, `title`, `published_at`, `fetched_at`: `NOT NULL` (matches the required-field list in `04-canonical-data-model.md`).
- `news_articles.canonical_url`: `NOT NULL UNIQUE`.
- `news_articles.content_hash`: `NOT NULL UNIQUE`.
- `UNIQUE (source, source_article_id) WHERE source_article_id IS NOT NULL` — a partial unique index, since `source_article_id` is legitimately null for GDELT.
- `news_articles.importance`: `CHECK (importance IS NULL OR (importance >= 0 AND importance <= 1))`.
- `news_articles.duplicate_of_id`: `REFERENCES news_articles(id)`, nullable, no `ON DELETE CASCADE` (deleting an article should not cascade-delete articles that reference it as a duplicate target — use `ON DELETE SET NULL`).
- `news_ingestion_logs.status`: `CHECK (status IN ('success', 'partial_failure', 'failure'))`.

### Indexes (and why each exists)

| Index | Reason |
|---|---|
| `idx_news_articles_published_at` (btree, `published_at DESC`) | Every "recent news" query and the "new news" overlap-window query (`09-ingestion-scheduler.md`) filters/sorts by this |
| `idx_news_articles_source` (btree) | Per-provider filtering, and joined with the ingestion-log reconciliation queries |
| `idx_news_articles_category` (btree) | The single most common downstream filter (per `01-news-classification.md`'s reasoning chain) |
| `idx_news_articles_country` (btree) | India-vs-global filtering is a first-class product need |
| `idx_news_articles_tickers` (GIN, on `tickers`) | Array-contains queries ("articles mentioning INFY") |
| unique index on `canonical_url` | Level-1 dedup (`07-deduplication.md`) — doubles as a lookup index |
| unique index on `content_hash` | Level-3 dedup — doubles as a lookup index |
| partial unique index on `(source, source_article_id)` | Level-2 dedup |
| `idx_news_ingestion_logs_run_started_at` (btree) | Scheduler needs to find "the last successful run" quickly for the overlap-window calculation |

No index is added for `url` itself (only `canonical_url`, which is what's actually queried/constrained), `content` (never filtered/sorted on directly — full-text search, if ever needed, is a `tsvector` concern deliberately deferred), or `author`/`image_url` (display-only fields, never filtered on).

## Implementation Steps

```text
Step 1 — Create a migrations directory (Alembic recommended, since the project is FastAPI/SQLAlchemy) and initialize it.
Step 2 — Write migration 001: create news_sources, seed with 4 rows (marketaux, finnhub, newsdata, gdelt) including license_type and stores_full_content columns.
Step 3 — Write migration 002: create news_categories, seed with the 7 rows from 01-news-classification.md.
Step 4 — Write migration 003: create news_articles with all columns, constraints, and indexes listed above.
Step 5 — Write migration 004: create news_entities, news_article_entities, news_topics, news_article_topics.
Step 6 — Write migration 005: create news_ingestion_logs.
Step 7 — Run all migrations against a local/dev database and verify with \d news_articles that every constraint and index above is present.
Step 8 — Implement database/repository.py with insert_article(), get_last_successful_run(), and log_ingestion_run() functions used by the scheduler and deduplication layers.
```

## Files to Create/Modify

```text
migrations/
├── 001_create_news_sources.py
├── 002_create_news_categories.py
├── 003_create_news_articles.py
├── 004_create_entity_topic_tables.py
└── 005_create_news_ingestion_logs.py
src/news/database/
├── __init__.py
├── session.py         # SQLAlchemy engine/session setup, reads DATABASE_URL
├── models.py           # SQLAlchemy ORM models mirroring the schema
└── repository.py        # insert_article, get_last_successful_run, log_ingestion_run, etc.
```

## Database Changes

### `news_sources`
```sql
CREATE TABLE news_sources (
    id TEXT PRIMARY KEY,                 -- 'marketaux' | 'finnhub' | 'newsdata' | 'gdelt'
    display_name TEXT NOT NULL,
    base_url TEXT,
    license_type TEXT,                   -- free text note, e.g. 'paid-commercial', 'free-metadata-only'
    stores_full_content BOOLEAN NOT NULL DEFAULT FALSE
);
```

### `news_categories`
```sql
CREATE TABLE news_categories (
    id TEXT PRIMARY KEY,                 -- e.g. 'company', 'geopolitical'
    label TEXT NOT NULL,
    description TEXT
);
```

### `news_articles`
```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE news_articles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source TEXT NOT NULL REFERENCES news_sources(id),
    source_article_id TEXT,
    url TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    content TEXT,
    author TEXT,
    image_url TEXT,
    published_at TIMESTAMPTZ NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL,
    language TEXT,
    country TEXT,
    category TEXT NOT NULL REFERENCES news_categories(id),
    subcategory TEXT,
    topics TEXT[],
    entities TEXT[],
    tickers TEXT[],
    companies JSONB,
    sentiment JSONB,
    importance NUMERIC CHECK (importance IS NULL OR (importance >= 0 AND importance <= 1)),
    content_hash TEXT NOT NULL,
    duplicate_of_id UUID REFERENCES news_articles(id) ON DELETE SET NULL,
    raw_payload_ref TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_news_articles_canonical_url UNIQUE (canonical_url),
    CONSTRAINT uq_news_articles_content_hash UNIQUE (content_hash)
);

CREATE UNIQUE INDEX uq_news_articles_source_article_id
    ON news_articles (source, source_article_id)
    WHERE source_article_id IS NOT NULL;

CREATE INDEX idx_news_articles_published_at ON news_articles (published_at DESC);
CREATE INDEX idx_news_articles_source ON news_articles (source);
CREATE INDEX idx_news_articles_category ON news_articles (category);
CREATE INDEX idx_news_articles_country ON news_articles (country);
CREATE INDEX idx_news_articles_tickers ON news_articles USING GIN (tickers);
```

### `news_entities` / `news_article_entities` / `news_topics` / `news_article_topics`
```sql
CREATE TABLE news_entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    entity_type TEXT,          -- 'company' | 'person' | 'organization' | 'country' | ...
    ticker TEXT,
    UNIQUE (name, entity_type)
);

CREATE TABLE news_article_entities (
    article_id UUID NOT NULL REFERENCES news_articles(id) ON DELETE CASCADE,
    entity_id UUID NOT NULL REFERENCES news_entities(id) ON DELETE CASCADE,
    role TEXT,                 -- 'mentioned' | 'primary_subject'
    PRIMARY KEY (article_id, entity_id)
);

CREATE TABLE news_topics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE news_article_topics (
    article_id UUID NOT NULL REFERENCES news_articles(id) ON DELETE CASCADE,
    topic_id UUID NOT NULL REFERENCES news_topics(id) ON DELETE CASCADE,
    PRIMARY KEY (article_id, topic_id)
);
```

### `news_ingestion_logs`
```sql
CREATE TABLE news_ingestion_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source TEXT REFERENCES news_sources(id),   -- NULL = whole-job-level log row
    run_started_at TIMESTAMPTZ NOT NULL,
    run_finished_at TIMESTAMPTZ,
    status TEXT NOT NULL CHECK (status IN ('success', 'partial_failure', 'failure')),
    articles_fetched INT DEFAULT 0,
    articles_inserted INT DEFAULT 0,
    articles_duplicate INT DEFAULT 0,
    articles_failed_validation INT DEFAULT 0,
    error_summary TEXT
);

CREATE INDEX idx_news_ingestion_logs_run_started_at ON news_ingestion_logs (run_started_at DESC);
```

## Configuration

```text
DATABASE_URL=postgresql://user:password@localhost:5432/finsight
```

## Testing

```text
- Test: inserting an article with a duplicate canonical_url raises IntegrityError, caught and handled by the repository layer.
- Test: inserting an article with a category not present in news_categories fails the FK constraint.
- Test: inserting an article with importance = 1.5 fails the CHECK constraint.
- Test: two articles from the same source with the same source_article_id conflict; two articles with source_article_id = NULL do not conflict with each other.
- Test: deleting an article that another article's duplicate_of_id points to sets that reference to NULL rather than failing or cascading.
```

## Expected Result

A running PostgreSQL database with all 7 tables, seeded lookup data, and every constraint/index from this document verifiable via `\d news_articles`.

## Acceptance Criteria

```text
- [ ] All 5 migrations run cleanly on a fresh database
- [ ] news_sources seeded with exactly 4 rows matching 02-api-selection.md
- [ ] news_categories seeded with exactly 7 rows matching 01-news-classification.md
- [ ] All constraints and indexes listed above exist and are verified
- [ ] repository.py implements insert_article, get_last_successful_run, log_ingestion_run
- [ ] Database-level tests pass
```

## Dependencies / Next Phase

`09-ingestion-scheduler.md` uses `repository.py`'s `get_last_successful_run()` to compute the "new news" overlap window, and `insert_article()`/`log_ingestion_run()` to persist results.

---

## ⚡ Actual Implementation Note (as-built)

> **The following reflects what is currently implemented in `models.py` and supersedes the 7-table design above for the active feature build.**

### Actual schema: single `articles` table

The live database uses **one table** (not seven). The equivalent DDL of what SQLAlchemy creates via `Base.metadata.create_all()` is:

```sql
CREATE TABLE articles (
    id              SERIAL PRIMARY KEY,
    title           VARCHAR,
    content         TEXT,
    source          VARCHAR,
    published_time  TIMESTAMP DEFAULT NOW(),
    url             VARCHAR UNIQUE,       -- Level-1 dedup constraint

    -- NLP & KG fields (populated by processing pipeline, NULL at insert time)
    sector          VARCHAR,
    confidence_score FLOAT,
    entities        JSON,                 -- [{text, category}] from NER
    processed       BOOLEAN DEFAULT FALSE,
    qdrant_point_id VARCHAR
);

-- Indexes (created by SQLAlchemy index=True)
CREATE INDEX ix_articles_id             ON articles (id);
CREATE INDEX ix_articles_title          ON articles (title);
CREATE INDEX ix_articles_source         ON articles (source);
CREATE INDEX ix_articles_published_time ON articles (published_time);
CREATE UNIQUE INDEX ix_articles_url     ON articles (url);
CREATE INDEX ix_articles_sector         ON articles (sector);
CREATE INDEX ix_articles_processed      ON articles (processed);
```

**Key differences from the 7-table plan:**
- No `news_sources`, `news_categories`, `news_entities`, `news_article_entities`, `news_topics`, `news_article_topics`, or `news_ingestion_logs` tables.
- `id` is `SERIAL` (integer), not `UUID`.
- `source` and `sector` are plain `VARCHAR`, not foreign keys into lookup tables.
- `entities` is a `JSON` column on the article row (not a normalized entity table + junction).
- No `content_hash`, `canonical_url`, `fetched_at`, `duplicate_of_id`, `importance`, `tickers`, `companies`, `sentiment`, `raw_payload_ref`, `language`, or `country` columns.
- No `news_article_embeddings` table — vector embeddings are stored externally in **Qdrant**, with `qdrant_point_id` on the article row as the join key.

### Repository layer

Ingestion and querying are implemented directly in `services.py` (no separate `repository.py`):
- `store_articles(db, articles)` — URL-dedup check + bulk insert.
- `seed_sample_news_if_empty(db)` — seeds 5 hardcoded articles when table is empty.
- `process_unprocessed_articles(db)` — queries `processed == False`, runs full NLP/KG pipeline, updates article row in-place.
- `search_articles_semantic(db, query, ...)` — queries Qdrant first, falls back to PostgreSQL ILIKE search.
