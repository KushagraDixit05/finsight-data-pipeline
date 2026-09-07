# 01 — News Classification

## Objective

Finalize the minimum useful set of news categories for FinSight AI, and the supporting fields (`subcategory`, `country_scope`, `tickers`, `companies`) that carry the rest of the nuance without exploding the category list.

## Why This Phase Exists

Every downstream piece — API selection, the canonical schema, the PostgreSQL `category` column and index, and eventually the reasoning chain (News → Region → Sector → Company → Portfolio Exposure) — depends on this taxonomy. Getting it wrong means a schema migration and a re-classification pass later. It has to be decided before anything else.

## Prerequisites

None. This is the first phase.

## Decisions

### What materially moves Indian stocks, global stocks, sectors, commodities, currencies, interest rates, and financial markets

Analysis of the drivers, grouped by causal pattern rather than by source publication (a "category" should represent *why something matters*, not *what section it appeared in*):

1. **Company-level events** — earnings, guidance changes, M&A, leadership changes, product news, corporate actions (buybacks, splits, dividends), credit rating changes, lawsuits. These move individual stocks directly and are the most common "impact" signal.
2. **Market-wide events** — index moves, IPOs, trading halts, broad sentiment shifts, sector rotations. These don't originate from one company but move many stocks together.
3. **Macroeconomic events** — GDP, inflation (CPI/WPI), employment, PMI, trade balance, fiscal deficit. These move whole markets and specific rate-sensitive sectors.
4. **Monetary policy events** — central bank rate decisions, QE/QT, RBI/Fed/ECB statements. These are macro in nature but deserve their own category because of how frequently and specifically portfolio reasoning needs to isolate "did a central bank act" from general macro noise, and because interest-rate sensitivity is one of the most common portfolio-exposure questions.
5. **Regulatory/government events** — new laws, SEBI/RBI regulatory changes, tax policy, government budgets, license approvals/denials, subsidies. Distinct from monetary policy: this is fiscal/administrative, not central-bank monetary action.
6. **Geopolitical events** — wars, sanctions, elections, diplomatic tensions, trade wars/tariffs, terrorism, major treaties. These move currencies, commodities, and risk sentiment globally, often cutting across many sectors at once.
7. **Commodities/energy/supply events** — oil price shocks, OPEC decisions, agricultural supply shocks, metal price moves, shipping/supply-chain disruption, natural disasters that affect production or supply.

### Why not more categories

The requirements document listed 15 candidate categories (Company, Markets, Economy/Macro, Central Bank, Government/Regulation, Geopolitical, Commodities/Energy, International, National/India, Corporate Earnings, M&A, IPO, Credit/Banking, Trade/Tariffs, Natural Disasters). Several of these are not independent *causal categories* — they are:

- **Scope, not category**: "International" vs "National/India" is a geography axis that applies to *every* category above (a `central_bank_monetary_policy` article can be about the RBI or the Fed). Modeling it as a separate top-level category would double the category count for no reasoning benefit. **Decision: model as a `country_scope` field**, not a category.
- **Subtype, not category**: "Corporate Earnings", "M&A", "IPO", "Credit/Banking" are all subtypes of `company` or `markets`. Splitting them into top-level categories fragments a single reasoning concept ("something happened to this company/sector") across multiple categories, making every future query need an OR-list instead of one filter. **Decision: model as a `subcategory` free-text tag** within the 7 categories, with a small controlled vocabulary suggestion (not enforced by a DB constraint, so it can grow without migrations): `earnings`, `guidance`, `mna`, `ipo`, `credit_rating`, `leadership_change`, `corporate_action`, `litigation`, `interest_rate_decision`, `qe_qt`, `inflation_data`, `gdp_data`, `employment_data`, `tariffs`, `sanctions`, `election`, `natural_disaster`, `supply_disruption`.
- **"Trade/Tariffs" and "Natural disasters"**: these are geopolitical/supply-chain in nature (tariffs are a trade-policy geopolitical act; natural disasters are supply-side commodity/economic shocks). **Decision: subcategory tags under `geopolitical` (tariffs, sanctions) or `commodities_energy` / `economy_macro` (natural disasters), not top-level categories.**

### Final recommended categories (7)

| `category` value | Covers | Typical subcategories |
|---|---|---|
| `company` | Single-company news that moves that stock directly | earnings, guidance, mna, ipo, leadership_change, corporate_action, credit_rating, litigation |
| `markets` | Market-wide, multi-stock, index/sector-level news not tied to one company or one macro release | index_move, sector_rotation, trading_halt, market_sentiment |
| `economy_macro` | Macroeconomic data and indicators | gdp_data, inflation_data, employment_data, pmi_data, trade_balance, fiscal_deficit |
| `central_bank_monetary_policy` | Central bank actions and statements | interest_rate_decision, qe_qt, central_bank_statement |
| `government_regulation` | Fiscal policy, law, regulatory bodies, government budgets | tax_policy, sebi_regulation, government_budget, subsidy, license_approval |
| `geopolitical` | Cross-border political/military/diplomatic events, trade policy | war_conflict, sanctions, election, tariffs, diplomatic_tension, terrorism |
| `commodities_energy` | Commodity, energy, and supply-chain events | oil_price, opec_decision, metals, agriculture, supply_disruption, natural_disaster |

This set is:
- **Simple**: 7 values, fits in a single `CHECK` constraint or lookup table, no ambiguity about where an article goes.
- **Useful for MVP**: covers every driver listed in the requirements without gaps.
- **Easy to maintain**: adding a new subcategory tag never requires a schema migration; adding a new top-level category (rare) does, and that's the correct trade-off — top-level categories should be rare and deliberate.
- **Useful for future AI reasoning**: the News → Region → Sector → Company chain filters primarily by `category` + `country_scope` + `tickers`/`companies`, all of which exist from day one.
- **Capable of identifying stock-relevant news**: `company` and `markets` map directly to tickers; the other 5 categories map to sector/portfolio exposure via downstream reasoning (out of scope for this pipeline, but the data shape supports it).

### `country_scope` values

Free-text ISO-3166 alpha-2 country code when the article is about one country's economy/market (`IN`, `US`, `CN`, ...), or one of the sentinel values `GLOBAL` (no single-country focus) or `MULTI` (explicitly about relations between 2+ named countries — store the countries in `entities`). Nullable — not every API reliably provides country.

## Implementation Steps

```text
Step 1 — Record this taxonomy as the single source of truth: this file.
Step 2 — Create the `news_categories` lookup table with exactly these 7 rows (done in 08-postgresql-schema.md; this phase only decides the values).
Step 3 — Ensure every adapter (05-api-adapters.md) maps its provider's category/section field to exactly one of these 7 values, defaulting to `markets` if unmappable, and puts anything more specific into `subcategory`.
Step 4 — Do not add an 8th top-level category without updating this file and running a migration; prefer a new `subcategory` value first.
```

## Files to Create/Modify

None yet — this is a decisions-only phase. The category list is consumed by `04-canonical-data-model.md`, `05-api-adapters.md`, and `08-postgresql-schema.md`.

## Database Changes

None in this phase (deferred to `08-postgresql-schema.md`, which creates `news_categories` seeded with these 7 rows).

## Configuration

None.

## Testing

None (no code yet). The taxonomy itself is validated indirectly in `11-testing.md` via adapter mapping tests (every provider category must map to one of the 7 values).

## Expected Result

A written, agreed taxonomy that every later phase references without re-litigating.

## Acceptance Criteria

```text
- [ ] 7 top-level categories finalized and documented
- [ ] country_scope modeled as a field, not a category
- [ ] subcategory modeled as a free-text tag with a suggested vocabulary, not a rigid enum
- [ ] Every candidate category from the original brainstorm list is explicitly mapped to either a top-level category, a subcategory, or the country_scope field
```

## Dependencies / Next Phase

`02-api-selection.md` uses this taxonomy to evaluate whether each candidate API's own categorization can be reasonably mapped onto it.
