# 04 — Canonical Data Model

## Objective

Define the single internal `NewsArticle` schema that every provider adapter must produce, with each field's type, nullability, source, and role fully specified.

## Why This Phase Exists

This is the contract between adapters and the rest of the pipeline (Rule 3). Normalization, validation, deduplication, storage, and embedding all operate on this shape and nothing else. Getting the required/optional/derived split right now avoids null-handling bugs and schema churn later.

## Prerequisites

`01-news-classification.md`, `02-api-selection.md`, `03-architecture.md` completed.

## Decisions

### Field classification

**Required fields** — every canonical article must have these, or validation rejects the record before it reaches the database:

| Field | Type | Notes |
|---|---|---|
| `source` | string | Our internal provider key: `marketaux`, `finnhub`, `newsdata`, `gdelt` |
| `url` | string (URL) | The article's canonical link; primary human-facing identifier |
| `title` | string | Max 500 chars (truncate, don't reject, if longer) |
| `published_at` | timestamptz | When the source says the article was published |
| `fetched_at` | timestamptz | When our pipeline retrieved it — always set by us, never by the provider |
| `category` | enum (7 values) | Set by the adapter's category-mapping rules (`01-news-classification.md`) |
| `content_hash` | string (sha256 hex) | Derived — computed by the normalizer, not the adapter |

**Optional fields** — may be null; not every provider supplies all of these:

| Field | Type | Notes |
|---|---|---|
| `source_article_id` | string, nullable | Provider's own article ID, if it exposes one (Marketaux, Finnhub, NewsData.io do; GDELT does not) |
| `description` | string, nullable | Short summary/snippet |
| `content` | string, nullable | Full or partial article body — **only populate if the provider's own response includes it and its license permits storage** (see `02-api-selection.md` open items); never populate for GDELT |
| `author` | string, nullable | |
| `image_url` | string (URL), nullable | |
| `language` | string (ISO 639-1), nullable | Default to `en` only if the provider's response is unambiguous about it; otherwise leave null rather than guess |
| `country` | string (ISO 3166-1 alpha-2), nullable | Maps to `country_scope` from `01-news-classification.md` |
| `subcategory` | string, nullable | Free-text tag from the suggested vocabulary |
| `raw_payload_ref` | string, nullable | Pointer to the stored raw provider response (for audit/debugging/reprocessing), not the payload itself |

**Derived fields** — computed by our own system, never taken from the provider:

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | Generated on insert (UUIDv7 preferred for time-ordering; UUIDv4 acceptable) |
| `canonical_url` | string | URL normalized per `06-normalization-validation.md` (lowercased host, tracking params stripped, trailing slash removed) — used for Level-1 dedup |
| `content_hash` | string | sha256 of `normalized_title + "|" + source + "|" + published_date (YYYY-MM-DD-HH)` — used for Level-3 dedup; see `07-deduplication.md` |
| `topics` | string[], nullable | Extracted/passed-through tags, provider-supplied where available |
| `entities` | string[], nullable | Named entities (people, orgs) — pass-through from provider if present; no in-house NLP extraction in MVP |
| `tickers` | string[], nullable | Stock ticker symbols — pass-through from provider if present (Marketaux and Finnhub supply these; GDELT and NewsData.io generally do not) |
| `companies` | jsonb, nullable | `[{"name": "...", "ticker": "..."}]` structured company mentions, pass-through where available |
| `sentiment` | jsonb, nullable | `{"label": "...", "score": ...}` — pass-through from provider if present; **no custom sentiment model in MVP** (Rule 10) |
| `importance` | numeric, nullable | 0.0–1.0 relative importance score; derived by a simple deterministic rule in MVP (see below), not a ML model |
| `duplicate_of_id` | UUID, nullable | Set by the deduplication step if this record is later identified as a near-duplicate of an existing row; null for the canonical/first-seen record |
| `created_at` / `updated_at` | timestamptz | Standard row bookkeeping, set by the database layer |

### `importance` — simple deterministic MVP rule (not ML)

To avoid inventing an unscoped scoring model, MVP importance is a simple, explainable formula:

```text
importance = base_score(category) + has_tickers_bonus + source_reliability_weight
```

Where `base_score` is a small lookup table (`central_bank_monetary_policy` and `geopolitical` start higher than `markets`), `has_tickers_bonus` adds weight if `tickers` is non-empty, and `source_reliability_weight` is a small per-provider constant. This is intentionally crude — it exists so the field isn't left completely empty, not to be a real ranking model. Document it as "deferred: real importance scoring" in the checklist.

### Which fields are required for vector embeddings

The embedding pipeline (`10-vector-db-integration.md`) concatenates and embeds: `title` + `description` (if present) + `content` (if present and license-permitted). It never embeds `raw_payload_ref`, `content_hash`, or bookkeeping timestamps. `category`, `subcategory`, `country`, `published_at`, `tickers`, `companies`, `topics`, `importance` are stored as **vector metadata** for filtering, not embedded as text.

### Which fields are indexed (summary — full detail in `08-postgresql-schema.md`)

Indexed: `published_at`, `source`, `category`, `country`, `content_hash` (unique), `canonical_url` (unique), `(source, source_article_id)` (unique, partial). `tickers` gets a GIN index since it's an array.

## Canonical JSON Example

See `00-overview.md` for the full worked example. Reproduced field list here matches exactly.

## Implementation Steps

```text
Step 1 — Define the NewsArticle model in src/news/models/news_article.py using Pydantic (preferred, for the free validation on type/format) or a dataclass + separate validator.
Step 2 — Define the 7-value category enum in src/news/models/enums.py, matching 01-news-classification.md exactly.
Step 3 — Define the NewsSource enum (marketaux, finnhub, newsdata, gdelt) in the same file.
Step 4 — Make all "optional" fields default to None; make all "derived" fields excluded from the adapter's construction signature (adapters must not set them — the normalizer/repository layer sets them).
Step 5 — Write a docstring on the model class that repeats the required/optional/derived split from this document, so the model is self-documenting in code.
```

## Files to Create/Modify

```text
src/news/models/
├── __init__.py
├── enums.py         # NewsCategory, NewsSource
└── news_article.py  # NewsArticle model
```

## Database Changes

None yet — the model here is the Python-layer contract; the table is created in `08-postgresql-schema.md` and must mirror these fields exactly.

## Configuration

None.

## Testing

```text
- Unit test: NewsArticle() raises a validation error if any required field is missing.
- Unit test: NewsArticle accepts all optional fields as None.
- Unit test: category field rejects any value outside the 7-value enum.
```

## Expected Result

A single, importable `NewsArticle` class that is the only object type passed between adapters, normalizers, deduplication, and the database layer.

## Acceptance Criteria

```text
- [ ] NewsArticle model implemented with required/optional/derived fields exactly as specified
- [ ] NewsCategory enum matches the 7 categories from 01-news-classification.md
- [ ] Adapters cannot set derived fields (enforced by constructor signature or a separate DerivedFields step)
- [ ] Model docstring documents required/optional/derived split
- [ ] Unit tests for required-field validation pass
```

## Dependencies / Next Phase

`05-api-adapters.md` builds one adapter per selected provider, each producing a `NewsArticle`.

---

## ⚡ Actual Implementation Note (as-built)

> **The following reflects what is currently implemented in `models.py` and `schemas.py` and supersedes the abstract plan above for the active feature build.**

The live codebase uses a simpler, flatter model reflecting the pipeline's two-phase nature: **ingestion** (raw fields from the provider) and **post-processing** (NLP-enriched fields added after the NLP/KG pipeline runs).

### SQLAlchemy ORM Model (`models.py` — `articles` table)

```python
class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)   # auto-increment int, not UUID
    title = Column(String, index=True)
    content = Column(Text, nullable=True)
    source = Column(String, index=True)
    published_time = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    url = Column(String, unique=True, index=True)         # uniqueness enforced here (Level-1 dedup only)

    # NLP & Knowledge Graph fields — populated post-processing, not at ingestion time
    sector = Column(String, index=True, nullable=True)           # replaces the 7-value category enum
    confidence_score = Column(Float, nullable=True)
    entities = Column(JSON, nullable=True)  # [{text, category}] list set by NER pipeline
    processed = Column(Boolean, default=False, index=True)       # True once NLP pipeline has run
    qdrant_point_id = Column(String, nullable=True)              # vector DB reference (Qdrant, not pgvector)
```

**Key differences from the abstract plan:**
- `id` is an **integer** primary key, not a UUID.
- Field is `published_time` (not `published_at`); no `fetched_at` field.
- No `content_hash`, `canonical_url`, or `duplicate_of_id` columns — URL uniqueness (`url UNIQUE`) is the sole dedup constraint.
- No separate `news_sources` / `news_categories` lookup tables — `source` and `sector` are plain strings.
- NLP-derived fields (`sector`, `confidence_score`, `entities`, `processed`, `qdrant_point_id`) live directly on the article row, populated post-insert by the processing pipeline.

### Pydantic Schemas (`schemas.py`)

```python
class ArticleCreate(BaseModel):
    title: str
    content: Optional[str] = None
    source: str
    published_time: datetime
    url: str

class Article(ArticleCreate):
    id: int
    sector: Optional[str] = None
    confidence_score: Optional[float] = None
    entities: Optional[List[Dict[str, str]]] = None
    processed: Optional[bool] = False
    qdrant_point_id: Optional[str] = None

    class Config:
        from_attributes = True
```

**Adapter outputs must produce `ArticleCreate`-compatible objects** — 5 fields required: `title`, `source`, `published_time`, `url`, plus optional `content`.

### EntityItem schema

```python
class EntityItem(BaseModel):
    text: str
    category: str  # ORG, LOC, COMMODITY, FINANCIAL_EVENT, etc.
```

Entities are stored as a JSON list of `{text, category}` dicts in the `entities` column, set by the NER pipeline post-ingestion.
