# 11 — Testing

## Objective

Consolidate the test requirements referenced throughout phases 04–10 into one concrete, phase-organized test plan, including fixtures and what "done" looks like for each layer.

## Why This Phase Exists

Section 17 of the requirements calls for tests at every layer. Each earlier phase already specified its own tests inline; this phase is where they're implemented as an actual test suite, plus the fixtures that make adapter/normalization tests possible without live API calls.

## Prerequisites

Phases `04` through `10` implemented.

## Decisions

- **Test runner**: `pytest`, matching the FastAPI/Python stack already in use.
- **No live network calls in the test suite.** Every adapter test uses a recorded fixture JSON file representing a real (or realistic, hand-constructed) response from that provider. This makes the suite fast, deterministic, and independent of API quota — running the tests never counts against Marketaux's 100-req/day limit, for example.
- **Database tests** run against a real (test/local) PostgreSQL instance, not a mock — constraints, FK behavior, and unique-violation handling are exactly the kind of thing that only a real database correctly exercises. Use a dedicated test database, created fresh per test run (or per test session, truncated between tests) via the same migrations as production.
- **Test data does not need to be exhaustive per provider** — one representative fixture with 2-3 articles per provider, plus a couple of deliberately malformed variants (missing title, missing published_at, HTML-laden title) is enough to exercise every normalization/validation rule.

## Implementation Steps

```text
Step 1 — Create tests/fixtures/ with one JSON file per provider: marketaux_sample.json, finnhub_sample.json, newsdata_sample.json, gdelt_sample.json, each containing 2-3 realistic articles.
Step 2 — Create tests/fixtures/malformed/ with a few deliberately broken variants (missing required field, malformed date, HTML-laden title) reused across normalization/validation tests.
Step 3 — Implement adapter tests (see table below).
Step 4 — Implement normalization/validation tests (already itemized in 06-normalization-validation.md).
Step 5 — Implement deduplication tests (already itemized in 07-deduplication.md).
Step 6 — Implement database tests (already itemized in 08-postgresql-schema.md).
Step 7 — Implement scheduler tests (already itemized in 09-ingestion-scheduler.md).
Step 8 — Implement the end-to-end test (see 12-end-to-end-integration.md).
Step 9 — Wire pytest into whatever CI mechanism the broader FinSight project already uses (out of scope to define here if it doesn't exist yet — just ensure `pytest` passes locally with a documented `pytest` invocation).
```

### API Adapter Tests (per provider)

```text
Given adapters/fixtures/<provider>_sample.json:
  - fetch_and_map() returns a NewsArticle for each article in the fixture
  - Every returned NewsArticle has all required fields populated (source, url, title, published_at, fetched_at, category)
  - category is always one of the 7 valid enum values, even for a fixture article whose provider-side category doesn't cleanly map (falls back to 'markets')
  - source is always the correct fixed provider key ('marketaux', 'finnhub', 'newsdata', 'gdelt')
  - GDELT adapter never populates `content`
  - Provider-specific date format parses to the correct UTC datetime (assert against a known expected value)
```

### Deduplication Tests

Already itemized in `07-deduplication.md`: same URL, same source ID, same content hash, genuinely different articles, and a simulated race condition.

### Database Tests

Already itemized in `08-postgresql-schema.md`: insert article, duplicate insert (each of the 3 unique constraints), required fields, foreign keys, importance CHECK constraint, duplicate_of_id ON DELETE SET NULL behavior.

### Scheduler Tests

Already itemized in `09-ingestion-scheduler.md`: job executes end-to-end with fixture adapters, a failed adapter doesn't stop others, running twice produces no duplicates, advisory lock contention is handled gracefully, fetch-window computation is correct on first run vs. subsequent runs.

### End-to-End Test

```text
Given fixture responses for all 4 providers (mocked at the HTTP layer, not the adapter layer, so the full adapter code path is exercised):
  1. Run the full pipeline: collector -> normalize -> validate -> dedup -> insert -> log
  2. Assert the expected number of rows landed in news_articles
  3. Assert news_ingestion_logs has one row per provider plus one overall row, with correct counts
  4. Re-run the exact same pipeline invocation
  5. Assert no new rows were inserted (idempotency) and the duplicate counts in the second run's log match the expected number
  6. (If phase 10 is implemented) assert every inserted article eventually has a corresponding news_article_embeddings row
```

Vector DB integration is **not required** in the earliest end-to-end test per the requirements — it's covered by phase 10's own tests and included in the end-to-end test only once phase 10 exists in the codebase.

## Files to Create/Modify

```text
tests/
├── fixtures/
│   ├── marketaux_sample.json
│   ├── finnhub_sample.json
│   ├── newsdata_sample.json
│   ├── gdelt_sample.json
│   └── malformed/
│       ├── missing_title.json
│       ├── missing_published_at.json
│       └── html_laden_title.json
├── test_adapters.py
├── test_normalization.py
├── test_validation.py
├── test_deduplication.py
├── test_database.py
├── test_scheduler.py
└── test_end_to_end.py
```

## Database Changes

None new — tests run migrations from `08-postgresql-schema.md` and `10-vector-db-integration.md` against a test database.

## Configuration

```text
TEST_DATABASE_URL=postgresql://user:password@localhost:5432/finsight_test
```

## Testing

(This phase *is* the testing phase — see Implementation Steps above.)

## Expected Result

`pytest` run from the project root exercises every layer of the pipeline without any live network calls, using a real test PostgreSQL database, and passes deterministically.

## Acceptance Criteria

```text
- [ ] Fixture files created for all 4 providers plus malformed-record variants
- [ ] Adapter tests pass for all 4 providers
- [ ] Normalization, validation, deduplication, database, and scheduler tests (as itemized in their respective phases) all pass
- [ ] End-to-end test passes, including the idempotency re-run assertion
- [ ] No test makes a live network call
- [ ] `pytest` documented as the single command to run the full suite
```

## Dependencies / Next Phase

`12-end-to-end-integration.md` is where the end-to-end test above is actually wired up and run as the final proof the whole pipeline works together.
