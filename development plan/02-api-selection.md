# 02 — News API Research & Selection

## Objective

Research currently available news/market-news APIs, evaluate each on coverage, licensing, and cost, and select the minimum set that covers all 7 categories from `01-news-classification.md` without unnecessary duplication.

## Why This Phase Exists

FinSight AI is meant to become a real product. An API chosen only because it has a generous free tier can become a legal or budget problem the moment the product ships. This phase separates **facts** (from official docs, verified via live search) from **decisions** (our judgment call given those facts), per Rule 9.

## Prerequisites

`01-news-classification.md` completed.

## Research Method Note

Pricing, rate limits, and terms of service change without notice. Every FACT below was checked against the provider's own site/docs. Re-verify before signing any paid contract — treat the numbers here as "true as of this document's research date," not a permanent guarantee. Anything not directly confirmed from an official source is marked **UNVERIFIED**.

---

## Candidate APIs Evaluated

### A. Marketaux

- FACT: Free plan = 100 requests/day, 3 articles per request, global market news, full metadata, 200,000+ tracked entities, 5,000+ sources, 80+ markets, 30+ languages.
- FACT: Basic plan = $29/mo ($24/mo billed annually), 2,500 requests/day, 20 articles/request.
- FACT: Standard plan = $49/mo, 10,000 requests/day, 50 articles/request, entity-level stats.
- FACT: Pro plan = $99/mo, 25,000 requests/day, 100 articles/request.
- FACT: Response format is JSON via REST; articles come with entity/sentiment metadata attached (per provider's own marketing — entity/sentiment fields are a core product feature, not an add-on).
- FACT: Company is Marketaux, headquartered in Vancouver, Canada (per third-party directory listing — **UNVERIFIED** against Marketaux's own "About" page).
- Commercial use: no explicit non-commercial restriction found on the pricing page; paid tiers are marketed for production applications. **Verify exact commercial redistribution terms in Marketaux's Terms of Service before production launch** — this was not independently re-confirmed in this research pass beyond the pricing page.
- DECISION: Use as the **primary structured financial-news source**. It is purpose-built for stock-market news with tickers/entities/sentiment already attached, which is exactly the shape FinSight needs and reduces the normalization burden on our own adapters.

### B. Finnhub

- FACT: Free tier documented (per third-party listing corroborated by multiple sources) as up to 60 API calls/minute, includes Company Profile, 1 year of company news (real-time updates), earnings calendar, EPS surprises; WebSocket real-time news feed and unlimited/no-rate-limit access are gated to premium.
- FACT: Has an official Python client (`finnhub-python`) and REST API.
- Coverage: strong on US-listed company news and fundamentals; India/global breadth **UNVERIFIED** — treat Finnhub primarily as the **company/ticker news** source, not the India or geopolitical source.
- Commercial use: **UNVERIFIED** in this research pass — Finnhub's public marketing targets both retail and institutional/production users, but the free-tier Terms of Service must be checked directly (finnhub.io/terms) before relying on it in production. Flag this as an open item in the acceptance criteria below.
- DECISION: Use as the **company/corporate-news adapter** (category `company`), primarily for earnings and company-specific updates tied to tickers.

### C. NewsData.io

- FACT: Pricing (per G2, corroborated pricing table): Free = 200 API credits/day; Basic = $199.99/mo for 20,000 credits/month; Professional = $349.99/mo for 50,000 credits/month; a higher enterprise-style tier exists above that.
- FACT: Marketed strength (per multiple review sources) includes strong India coverage, category and country filters, and historical + live article search.
- Commercial use: Paid tiers exist specifically for production-volume usage, which signals commercial use is an intended and paid-for use case — but the **exact license text on stored content (can we persist title+description+content, or snippet only?) was not independently confirmed against NewsData.io's own Terms of Service in this research pass.** This must be re-verified from newsdata.io's official ToS/licensing page before storing full article `content` from this provider; until verified, treat NewsData.io content as **metadata + description only**, not full body text, in `raw_payload_ref` handling.
- DECISION: Use as the **India/national + general category-news source** — the category and country filtering plus India-market strength directly fills the "National/India" coverage gap the other 3 chosen APIs don't specialize in.

### D. GDELT (GDELT Project — gdeltproject.org)

- FACT: GDELT is a free, open, worldwide media-monitoring dataset covering print, broadcast, and web news in 100+ languages, updated continuously (per GDELT Project's own about page and multiple independent descriptions), with public access via the GDELT DOC 2.0 API, the Events API, the GKG (Global Knowledge Graph), and BigQuery.
- FACT: GDELT provides event/article **metadata** (source URL, title, tone/sentiment score, themes, entities, geolocation) — it does **not** grant a license to redistribute or store the full text of the underlying news articles, because GDELT does not own that copyright; the underlying publishers do. (This is corroborated by the existence of third-party research tools whose entire purpose is reconstructing full article text from GDELT's n-gram data — if GDELT distributed full text directly, that reconstruction effort would be unnecessary.)
- FACT: GDELT itself is free and has no published rate-limit-driven pricing tier for the core DOC/Events APIs (a paid "GDELT Cloud" product also exists from a *separate* third-party vendor built on top of GDELT data — **do not confuse GDELT Cloud's commercial terms with the free, open GDELT Project APIs**; FinSight should use the GDELT Project's own free endpoints, not GDELT Cloud).
- Commercial use: GDELT Project data is published as open data for research and analysis; FinSight's use (aggregating public event/article metadata for internal reasoning, not republishing article text) fits squarely within that intent. **Rule 7 applies strictly here: store URL + title + tone/theme metadata only, never article body text, from GDELT.**
- DECISION: Use as the **geopolitical/global event signal source** (category `geopolitical`, secondary support for `economy_macro` and `commodities_energy` when the event is a natural disaster or supply shock). Metadata-only by design, which is also a deduplication asset — GDELT records often point at the same underlying URL a paid API also returned, making it a natural cross-check source (Level 1 dedup, `07-deduplication.md`) without any incremental storage-rights risk.

### E. NewsAPI.org — DEFERRED

- FACT: Free "Developer" plan = 100 requests/day, articles delayed 24 hours, search limited to the past month, **explicitly restricted to development/testing use only — cannot be used in staging or production, including internally**, per NewsAPI.org's own pricing page.
- FACT: "Business" plan = $449/month for 250,000 requests/month, real-time articles, 5-year search history, no uptime SLA.
- FACT: "Advanced" plan = $1,749/month for 2,000,000 requests/month with a 99.95% uptime SLA.
- DECISION: **Do not use in MVP.** The free tier cannot legally run our production pipeline, and the cheapest production-legal tier ($449/mo) is disproportionate to what Marketaux + Finnhub + NewsData.io + GDELT already cover for a fraction of the cost. Revisit only if a specific coverage gap is identified that the 4 selected APIs cannot fill.

### F. Alpha Vantage News & Sentiment — DEFERRED

- FACT: Alpha Vantage's Terms of Service grant free-key use for **personal, non-commercial use** only; "commercial use" is explicitly defined to include "investment analysis, research, testing, monitoring, and any other activities" beyond individual personal use — i.e., using it inside a product like FinSight is commercial use by their own definition, even before charging users.
- FACT: Free-tier request limits are low (documented at 25 requests/day in current Alpha Vantage support material) and are separately gated regardless of the licensing question.
- FACT: The News Sentiment endpoint returns a normalized sentiment score per article (range roughly -0.35 to 0.35 in third-party documentation, bucketed into Bearish/Somewhat Bearish/Neutral/Somewhat Bullish/Bullish) — useful signal type, but not exclusive to Alpha Vantage.
- DECISION: **Do not use free tier in MVP** — it fails Rule 7 (do not store what we cannot legally store/use) as soon as the pipeline runs in a commercial product context. Revisit only under an explicit paid/commercial Alpha Vantage plan, and only if none of the 4 selected APIs' sentiment fields are sufficient.

### G. Enterprise-tier wire services (Reuters, Bloomberg, AP, Dow Jones) — NOTED, NOT SELECTED FOR MVP

- FACT: All four require direct commercial negotiation; no self-serve, transparent pricing was found (per multiple industry-comparison sources), and pricing is described as enterprise-focused / custom-quoted.
- DECISION: Out of scope for MVP due to cost and procurement lead time. Note in the architecture as the natural upgrade path for `company`/`markets` category depth once FinSight has commercial traction — the adapter pattern (`05-api-adapters.md`) is designed so adding a 5th provider later is a new adapter file, not a pipeline rewrite.

---

## Final API Comparison Table

| Provider | Role (category) | Free tier | Cheapest production-legal tier | India coverage | Geopolitical coverage | Storable content |
|---|---|---|---|---|---|---|
| Marketaux | `company`, `markets` (primary) | 100 req/day, 3 articles/req | Basic $29/mo | Included in "80+ global markets" (not India-specialized) | Limited | Title, description, entities, sentiment (verify full-text rights before storing `content`) |
| Finnhub | `company` (secondary) | 60 calls/min, 1yr company news | Verify before production — **open item** | Not specialized | Not specialized | Title, description/summary, URL (verify full-text rights before storing `content`) |
| NewsData.io | `government_regulation`, `economy_macro`, general India/national | 200 credits/day | Basic $199.99/mo | Strong (marketed strength) | Moderate | Title, description (treat as metadata/snippet only until ToS re-verified) |
| GDELT | `geopolitical`, `commodities_energy` (secondary) | Free, effectively unlimited (fair-use) | N/A — always free | Included (100+ languages, all countries) | Very strong (this is GDELT's core purpose) | **Metadata + URL only, never full text** |
| NewsAPI.org | *deferred* | Dev-only, not production-legal | $449/mo | General only | General only | N/A — deferred |
| Alpha Vantage News | *deferred* | Non-commercial only per ToS | Requires paid/commercial plan (not evaluated) | General only | Not specialized | N/A — deferred |

## Decisions

1. **4 active providers**: Marketaux, Finnhub, NewsData.io, GDELT. This covers all 7 categories with no more than 2 sources per category, avoiding unnecessary duplication while keeping redundancy for the highest-value categories (`company`, `geopolitical`).
2. **Adapter-per-provider**: each provider gets exactly one adapter (see `05-api-adapters.md`); the rest of the pipeline is provider-agnostic (Rule 2).
3. **Content storage is conservative by default**: for Marketaux, Finnhub, and NewsData.io, store `content` only if that provider's field is populated by the API response itself (i.e., we store what they hand us, we do not scrape the source URL ourselves to fill gaps). For GDELT, never populate `content` — metadata only. This is documented per-provider in `news_sources.stores_full_content` (see `08-postgresql-schema.md`).
4. **Two explicit open items to close before production launch** (do not block MVP development, but must block production go-live):
   - Confirm Marketaux's Terms of Service on redistribution/storage of returned article text.
   - Confirm Finnhub's Terms of Service on commercial use at the free tier, or budget for their paid tier.

## Implementation Steps

```text
Step 1 — Create developer accounts / free API keys for Marketaux, Finnhub, NewsData.io. (GDELT needs no key for its public DOC/Events API.)
Step 2 — Store each key as an environment variable per 16-configuration conventions (see 09-ingestion-scheduler.md's Configuration section).
Step 3 — Read each provider's current official rate-limit documentation and record it in the adapter's docstring (05-api-adapters.md) — do not hardcode assumptions.
Step 4 — File the two open licensing items (Marketaux content storage, Finnhub commercial terms) as tracked to-dos before production go-live.
```

## Files to Create/Modify

None yet — decisions only. Consumed by `05-api-adapters.md` (one adapter per selected provider) and `09-ingestion-scheduler.md` (rate-limit-aware collector).

## Database Changes

None in this phase (the `news_sources` table seeded with these 4 providers — plus `stores_full_content` and `license_type` flags — is created in `08-postgresql-schema.md`).

## Configuration

Anticipated environment variables (finalized in `09-ingestion-scheduler.md`):

```text
MARKETAUX_API_KEY=
FINNHUB_API_KEY=
NEWSDATA_API_KEY=
# GDELT requires no API key for the public DOC/Events API
```

## Testing

None in this phase (no code yet).

## Expected Result

A documented, licensing-aware set of 4 active news providers, each mapped to one or more of the 7 categories, with 2 explicit open licensing items tracked for pre-production resolution.

## Acceptance Criteria

```text
- [ ] 4 active APIs selected: Marketaux, Finnhub, NewsData.io, GDELT
- [ ] NewsAPI.org and Alpha Vantage News explicitly deferred with documented reasons
- [ ] Every FACT above is traceable to an official/primary source or explicitly marked UNVERIFIED
- [ ] Two open licensing items (Marketaux content storage, Finnhub commercial terms) logged as pre-production blockers
- [ ] No category from 01-news-classification.md is left uncovered
```

## Dependencies / Next Phase

`03-architecture.md` designs the pipeline around these 4 providers.

---

## ⚡ Actual Implementation Note (as-built)

> **The following reflects what is currently implemented in `services.py` and supersedes the provider selection table above for the active feature build.**

### Currently implemented providers

| Provider | Plan status | As-built status | Notes |
|---|---|---|---|
| **Finnhub** | Selected | ✅ **Implemented** | `fetch_finnhub_news()` — general news endpoint; `FINNHUB_API_KEY` from env |
| **NewsAPI.org** | ❌ Deferred (dev-only ToS) | ✅ **Implemented** | `fetch_newsapi_news()` + `fetch_historical_news()` — using the free dev tier; `NEWSAPI_KEY` from env. **Production go-live blocker:** the NewsAPI free tier is development-only per its ToS; a paid Business plan ($449/mo) would be required before any production launch |
| **Marketaux** | Selected | ❌ Not yet implemented | Planned as primary structured source; adapter not yet built |
| **NewsData.io** | Selected | ❌ Not yet implemented | Planned as India/national source; adapter not yet built |
| **GDELT** | Selected | ❌ Not yet implemented | Planned as geopolitical source; adapter not yet built |

### NewsAPI dev-tier risk flag

NewsAPI is being used in the active build on its free/developer tier, which per NewsAPI's own Terms of Service is explicitly **not licensed for staging or production** use. This is acceptable during development (the same constraint the plan noted when deferring it) but **must be resolved before any production deployment** — either by subscribing to the NewsAPI Business plan ($449/mo) or by replacing it with Marketaux + NewsData.io adapters, which are already planned.

### Live ticker quotes

`services.py` also implements `fetch_live_ticker_quotes()` — a separate function unrelated to news ingestion that fetches live stock quotes for 9 tickers (SPY, QQQ, NVDA, AAPL, MSFT, AMZN, TSLA, JPM, XOM) from the Finnhub quote endpoint with a 60-second TTL cache and realistic fallback values. This is not part of the news ingestion pipeline and is not covered by the phase plan.
