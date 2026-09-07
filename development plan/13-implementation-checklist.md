# 13 — Master Implementation Checklist

This is the single ordered checklist for the whole News Data Collection and Storage Pipeline. Each item links back to the phase file where it's specified in detail.

## Phase 01 — News Classification
```text
- [ ] 7 top-level categories finalized (01-news-classification.md)
- [ ] country_scope and subcategory modeled as fields, not extra categories
```

## Phase 02 — API Selection
```text
- [ ] APIs selected: Marketaux, Finnhub, NewsData.io, GDELT (02-api-selection.md)
- [ ] NewsAPI.org and Alpha Vantage News explicitly deferred with reasons documented
- [ ] API licenses reviewed; two open items logged: Marketaux content-storage terms, Finnhub commercial-use terms
```

## Phase 03 — Architecture
```text
- [ ] Folder structure created (03-architecture.md)
- [ ] Scheduler mechanism decided: cron + PostgreSQL advisory lock
- [ ] Fault-isolation principle documented
```

## Phase 04 — Canonical Data Model
```text
- [ ] NewsArticle model implemented with required/optional/derived fields (04-canonical-data-model.md)
- [ ] NewsCategory enum matches the 7 finalized categories
```

## Phase 05 — API Adapters
```text
- [ ] All 4 adapters implemented (05-api-adapters.md)
- [ ] GDELT adapter never populates content
- [ ] Collector isolates per-adapter failures
```

## Phase 06 — Normalization & Validation
```text
- [ ] All 11 normalization rules implemented in order (06-normalization-validation.md)
- [ ] Validation rejects malformed records with logged reasons without stopping the batch
```

## Phase 07 — Deduplication
```text
- [ ] check_duplicate() implemented (Levels 1-3) (07-deduplication.md)
- [ ] Near-duplicate (Level 4) explicitly deferred, schema reserved via duplicate_of_id
```

## Phase 08 — PostgreSQL Schema
```text
- [ ] All 7 tables created with documented constraints and indexes (08-postgresql-schema.md)
- [ ] news_sources and news_categories seeded correctly
- [ ] repository.py implemented
```

## Phase 09 — Ingestion Scheduler
```text
- [ ] Advisory lock prevents overlapping runs (09-ingestion-scheduler.md)
- [ ] Overlap-window "new news" strategy implemented
- [ ] Full error-handling table implemented
- [ ] Rate limits configured, not hardcoded
- [ ] Crontab entry deployed
```

## Phase 10 — Vector DB Integration
```text
- [ ] pgvector selected over separate Pinecone/Weaviate for MVP, with migration path documented (10-vector-db-integration.md)
- [ ] news_article_embeddings table created
- [ ] Embedding generation decoupled and failure-isolated from ingestion
```

## Phase 11 — Testing
```text
- [ ] Fixtures created for all 4 providers plus malformed-record variants (11-testing.md)
- [ ] Adapter, normalization, validation, deduplication, database, and scheduler tests all pass
- [ ] No live network calls in the automated suite
```

## Phase 12 — End-to-End Integration
```text
- [ ] Full pipeline run successfully against real API keys in a dev environment (12-end-to-end-integration.md)
- [ ] Idempotency proven against real data (second run inserts ~0 new rows)
- [ ] Simulated provider failure correctly isolated
```

## Cross-Cutting / Final Sign-off
```text
- [ ] News categories finalized
- [ ] APIs selected and licenses verified (open items closed before production go-live, not before MVP dev)
- [ ] Architecture finalized
- [ ] Canonical schema finalized
- [ ] PostgreSQL schema created
- [ ] API adapters implemented
- [ ] Normalization implemented
- [ ] Deduplication implemented
- [ ] Scheduler implemented
- [ ] Tests implemented
- [ ] End-to-end ingestion working
- [ ] Vector integration prepared
- [ ] MVP simplification review complete: every deferred component has a documented reason and a documented trigger condition for revisiting it (see 00-overview.md's simplification table)
```

## Explicitly Out of Scope for This Checklist (do not add mid-build without updating the requirements)

```text
- Portfolio impact analysis / reasoning chain (News -> Region -> Sector -> Company -> Exposure)
- LLM-based reasoning over retrieved news
- Recommendation generation
- Frontend/UI work
- Knowledge graph / event-relationship modeling
- Custom sentiment or importance ML models
- Near-duplicate/semantic deduplication (Level 4)
- Separate Pinecone/Weaviate deployment
- Celery / Airflow / Kafka
```
