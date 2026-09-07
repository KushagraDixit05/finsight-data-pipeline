# FinSight AI — Project Context

**Version:** 0.1 (Concept / Pre-Development Stage)
**Last updated:** March 2026 (knowledge doc) + strategy discussion, July 2026
**Status:** Confidential — Internal Use Only

---

## 1. What FinSight AI Is

FinSight AI is an AI-powered **vertical portfolio management platform** designed to act as a personal financial advisor and wealth manager for everyday users. Unlike generic finance apps that passively display data, FinSight AI actively reasons about a user's complete financial position — investments, bank accounts, assets, liabilities, and insurance — and combines this with real-time market data and financial/geopolitical news to generate personalized insights, risk assessments, and goal-based recommendations.

**Core vision statement:**
> "Give every person — regardless of income or financial literacy — access to an intelligent, always-on financial co-pilot that understands their complete financial picture and helps them make better decisions every day."

### What FinSight AI is NOT
- Not a trading bot or algorithmic execution system — it advises, it does not execute trades autonomously.
- Not a replacement for SEBI-registered human advisors — it is a decision-support layer.
- Not a generic chatbot — every response is grounded in the user's actual financial data.

---

## 2. The Problem

- Retail investors and salaried professionals lack access to the real-time, personalized financial intelligence that institutional investors enjoy.
- Existing apps (Zerodha, Groww, ET Money) are passive tools — they show data but don't reason about it.
- Professional wealth managers are expensive and inaccessible to the middle-income segment.
- Global news and geopolitical events move markets, but most users can't connect macro events to their own portfolios.

### Target Users
- Salaried professionals (25–50) with equities, mutual funds, and fixed deposits.
- First-generation investors who lack experience interpreting market movements.
- HNIs wanting a second layer of AI-driven insight alongside human advisors.
- Small business owners managing personal + business finances together.

---

## 3. Strategic Goals

| Horizon | Goal |
|---|---|
| **Short-term (MVP)** | Prototype the core AI reasoning loop: ingest portfolio → ingest market data → ingest news → generate personalized, actionable suggestions. |
| **Medium-term (V1)** | Consumer web/mobile app; integrate Zerodha Kite, Groww, Angel One SmartAPI, banking APIs; pursue SEBI RIA compliance or partner with a licensed advisor; reach 10,000 active users. |
| **Long-term** | Multi-market expansion (India, US/SEC-FINRA, UAE, UK); proprietary fine-tuned LLM on Indian market/SEBI/RBI data; B2B2C white-label channel for banks/NBFCs/wealth firms; become the default AI financial co-pilot for the Indian middle class. |

---

## 4. Planned Features (nothing currently live)

### Priority 1 — Core / MVP
- **Persistent Portfolio Context** — secure ingestion of equities, MFs, bank balances, FDs, crypto, real estate; broker/bank API sync (Zerodha Kite, Angel One, Plaid); portfolio injected into every AI conversation via RAG; manual entry fallback.
- **Real-Time Market Intelligence** — NSE/BSE, commodities, currencies, global indices; sector-level exposure analysis; plain-English market digests.
- **Global News Monitoring & Impact Analysis** — ingestion from Reuters, Bloomberg, Moneycontrol, ET, GDELT, AP; relevance scoring (sector/sentiment/time horizon); personal impact mapping (e.g., "Rising crude oil prices could affect your ONGC and HPCL positions").
- **Personalized Financial Suggestions** — goal-based advice, emergency-fund monitoring, rebalancing suggestions, tax optimization hints (LTCG/STCG, Section 80C).

### Priority 2 — V1 Enhancements
- Risk Profile Engine (dynamic, adjusts to volatility/life events).
- Goal Simulator (Monte Carlo wealth projections).
- Smart Alerts (price drops, RBI decisions, earnings).
- Portfolio Stress Testing (2008 crisis, COVID crash, 2013 taper tantrum).
- Competitor/benchmark comparison (Nifty 50, Nifty Midcap, category averages).

### Priority 3 — Aspirational (V2+)
- Voice interface for portfolio queries.
- Family Financial Hub (multi-member household view).
- Document Intelligence (SIP statements, ITR filings, insurance, salary slips).
- Behavioral Coaching (panic-sell detection, overtrading nudges).
- Proprietary fine-tuned domain LLM.

---

## 5. Technical Architecture

FinSight AI is a **vertical AI application** — built on top of existing LLMs, not trained from scratch.

**Six-layer architecture:**
1. **User Interface** — Web / Mobile app + conversational chat.
2. **Orchestration Engine** — LangChain / LlamaIndex agent decides what data to fetch and how to compose prompts.
3. **Context Assembly** — Portfolio DB + market feed + news pipeline injected via RAG.
4. **AI Reasoning Core** — LLM API (Claude / GPT-4o / Gemini Pro).
5. **Quantitative Models** — narrow ML models (risk scoring, price-impact estimation, anomaly detection).
6. **Data Infrastructure** — PostgreSQL (structured data), Pinecone/Weaviate (vector embeddings), Redis (caching).

### Key Technology Choices

| Component | Choice | Rationale |
|---|---|---|
| LLM Core | Claude 3.5 / GPT-4o (API) | Best-in-class reasoning, no training cost |
| Orchestration | LangChain / LlamaIndex | Mature agentic frameworks, large community |
| Vector DB | Pinecone or Weaviate | Fast semantic search over financial documents |
| Structured DB | PostgreSQL | ACID compliance for financial transaction data |
| Market Data | Polygon.io / NSE API / Alpha Vantage | Reliable, low-latency feeds |
| News Pipeline | NewsAPI + GDELT + Reuters RSS | Broad financial + geopolitical coverage |
| Backend | Python (FastAPI) | Best ML/AI ecosystem |
| Frontend | React + React Native | Shared codebase, web + mobile |
| Cloud | AWS / GCP | Scalable, good ML tooling |

### Training vs. No Training
- **No training from scratch** — foundation LLMs used via API (training would cost $50M–$500M).
- **Optional Phase 2 fine-tuning** — Llama 3 70B on Indian financial data (SEBI filings, earnings calls, RBI docs); est. $20K–$100K.
- **Narrow ML models (Phase 1)** — XGBoost/LSTM trained on historical market data for price-impact scores, volatility forecasting, risk scoring; cheap and effective.

---

## 6. Current Progress (as of the March 2026 knowledge doc)

| Area | Status |
|---|---|
| Overall Project Stage | Pre-development — research & planning |
| Architecture Design | Completed (initial draft) |
| Technology Stack | Completed (selected) |
| Product Requirements | In progress |
| Development | Not started |
| Regulatory Research | Not started |
| Team Formation | Not started |
| Funding | Not started |

**Completed so far:** concept definition, architecture design (all 6 layers), tech stack selection with rationale, feature list across 3 priority tiers, understanding of RAG vs. fine-tuning vs. narrow ML, cost estimation framework, project knowledge documentation.

**Immediate next steps:**
1. Finalize detailed PRD with user stories and acceptance criteria.
2. SEBI regulatory research — RIA registration, consult a financial regulatory lawyer.
3. Build a proof-of-concept — connect Claude/GPT-4o API to a static sample portfolio and demonstrate basic reasoning.
4. Recruit co-founders / key technical hires (backend, ML engineer).
5. Define fundraising strategy (bootstrapped MVP vs. pre-seed raise).

---

## 7. Resource & Cost Estimates

### MVP Phase (Months 1–9)
| Resource | Estimated Cost (INR) | Notes |
|---|---|---|
| Engineering team (3) | ₹60L – ₹1.2Cr/year | Backend, ML, Frontend |
| LLM API costs | ₹40K – ₹4L/month | Scales with users |
| Market data feeds | ₹15K – ₹2L/month | Polygon.io, NSE API |
| Cloud infra | ₹40K – ₹2.5L/month | DB, compute, pipelines |
| Legal & regulatory | ₹10L – ₹20L (one-time) | SEBI RIA consultation |
| Misc (tools, design, QA) | ₹5L – ₹10L (one-time) | Setup costs |

### Optional Model Fine-Tuning (Phase 2)
| Activity | Cost | Timeline |
|---|---|---|
| GPU compute (Llama 3 70B) | $20K – $100K | 2–3 months |
| Training data curation/labeling | $10K – $30K | 2–3 months parallel |
| ML engineering | ₹30L – ₹60L/year | Ongoing |

> Fine-tuning is optional for MVP — the initial product should be built entirely on LLM APIs (Claude, GPT-4o) via RAG and prompt engineering. Fine-tuning is only relevant post-MVP validation.

---

## 8. Regulatory & Risk Considerations (India)

- **SEBI RIA** — Registered Investment Advisor license required for personalized investment advice (₹5,000 fee for individuals; qualification/net-worth requirements apply).
- **SEBI RA** — Research Analyst registration may be required for publishing market analysis.
- **RBI** — governs any product touching banking/payment data (relevant once bank APIs are integrated).
- **DPDP Act 2023** — user financial data is sensitive personal data; requires explicit consent, data minimization, right-to-erasure compliance.

### Risk Mitigations
- Frame outputs as "insights, analysis, and education," not "personalized investment advice," to avoid needing SEBI RIA during MVP.
- Prominent disclaimers: *"This is not SEBI-registered investment advice. Consult a qualified advisor before making investment decisions."*
- Human-in-the-loop layer for high-stakes suggestions early on.
- Communicate AI uncertainty clearly — avoid false confidence.

### Data Security Requirements
- End-to-end encryption at rest and in transit (AES-256, TLS 1.3).
- OAuth 2.0 for all broker/bank integrations — no plain-text credential storage.
- SOC 2 Type II as a target for institutional partnerships.
- Zero-data-retention option for users who delete accounts.

---

## 9. Development Roadmap

| Phase | Timeline | Key Deliverables |
|---|---|---|
| Phase 0 — Foundation | Months 1–2 | PRD finalized, regulatory lawyer engaged, PoC built, team hired |
| Phase 1 — MVP Build | Months 3–6 | Portfolio ingestion, LLM reasoning core, basic news pipeline, web app alpha |
| Phase 2 — MVP Launch | Months 7–9 | Broker API integrations, closed beta (100 users), feedback loops |
| Phase 3 — V1 Product | Months 10–15 | Smart alerts, goal simulator, stress testing, mobile app, 1,000 users |
| Phase 4 — Scale | Months 16–24 | Fine-tuned model, B2B2C partnerships, multi-market expansion, 10K+ users |

---

## 10. Competitive Landscape

| Competitor | What they do | What they lack |
|---|---|---|
| Zerodha / Groww | Stock & MF trading platforms | No AI reasoning; no personalized advice; data display only |
| ET Money / Kuvera | MF investment & goal tracking | No real-time market intelligence; limited AI; no holistic view |
| Smallcase | Thematic portfolio baskets | Not personalized; no AI advisor layer |
| INDmoney | Multi-asset aggregation | Aggregation without intelligent reasoning |
| Betterment / Wealthfront (US) | Robo-advisors | Rule-based, not LLM-powered; US-only |
| **PortoAI (India)** | Connects to Zerodha/Groww, answers exposure/overlap questions | Closest direct competitor |
| **Finapolis** | AI investment companion — research, screening, reporting, trading, monitoring | Also a close competitor |

### FinSight AI's Differentiation
- Only platform combining persistent portfolio memory + real-time market data + global news analysis + LLM-powered personalized reasoning.
- Reasons about the user's *specific* situation, not generic commentary.
- Goal-centric: every suggestion tied to stated financial goals and time horizons.
- Built for India from the ground up — understands SIPs, PPF, ELSS, SGBs, REITs, taxation, and regulatory context.

---

## 11. Glossary

| Term | Definition |
|---|---|
| LLM | Large Language Model — trained on massive text corpora (GPT-4o, Claude, Gemini). |
| RAG | Retrieval-Augmented Generation — injecting external data into an LLM's context at query time without retraining. |
| Fine-tuning | Retraining a pretrained model on domain-specific data; cheaper than training from scratch. |
| Vertical AI | An AI system built for a specific industry domain using existing AI infrastructure. |
| Orchestration | Coordinating tools/APIs/data sources to compose the right context before querying the LLM. |
| Vector Database | DB optimized for storing/searching high-dimensional embeddings (semantic search). |
| SEBI RIA | Securities and Exchange Board of India — Registered Investment Advisor license. |
| DPDP Act | Digital Personal Data Protection Act, 2023 — India's data privacy law. |
| Monte Carlo Simulation | Random-sampling technique to model probability of financial outcomes. |
| LTCG / STCG | Long-Term / Short-Term Capital Gains — Indian tax categories based on holding period. |

---

## 12. Strategic / Research Discussion (July 2026)

### Where FinSight AI sits in the evolution of AI financial advisors

| Generation | Era | Characteristics | Examples |
|---|---|---|---|
| Gen 1 | 2015–2022 | Rule-based robo-advisors: risk profile, age, goals, asset allocation. No understanding of *why* markets move. | Betterment, Wealthfront, Groww recommendations |
| Gen 2 | 2023–2024 | LLMs enter finance; retrieval-based summarization of news/reports/opinions. | Early LLM finance chatbots |
| Gen 3 | 2025 | Portfolio-aware AI: inspects actual holdings before explaining events. | Charles Schwab, Vanguard Expert Insights, PortoAI |
| **Gen 4 (target)** | 2026+ | Multi-agent, causal, event-propagation reasoning tied to an individual's specific portfolio exposure. | FinSight AI's proposed direction |

### Key research directions identified as relevant
1. **Multi-Agent Systems** — teams of specialized agents (News, Portfolio, Macro, Risk, Valuation, Sentiment, Tax, Execution) coordinated by an "investment committee" meta-agent, rather than a single LLM call. Reference point: a "Self-Driving Portfolio" architecture using ~50 specialized agents with critique/voting.
2. **Event → Portfolio Impact** — asking not "what happened" but "does this news actually matter for *this* user's holdings," e.g., mapping a Taiwan earthquake to Nvidia exposure via TSMC dependency.
3. **Causal Reasoning Chains** — News → Economic Event → Affected Industries → Affected Companies → Portfolio Exposure → Risk Score → Recommendation (vs. plain summarization).
4. **Portfolio Memory** — persistent memory of salary, SIP dates, emergency fund, past decisions, risk tolerance, and goals, so recommendations reference prior context rather than being generic.
5. **Explainable AI** — every recommendation must show its reasoning chain/evidence, given regulatory sensitivity around black-box financial advice.
6. **Scenario Simulation** — multi-scenario "what-if" projections (e.g., rate cuts, oil price spikes, geopolitical tension) rather than single fixed predictions.

### Existing products referenced
- **Charles Schwab** — combines portfolio performance, market news, and research commentary into personalized client explanations; expanding into concentration-risk/allocation insights.
- **Vanguard (Expert Insights)** — advisor-facing tool converting portfolio data into client-ready recommendations grounded in Vanguard's methodology.
- **PortoAI (India)** — connects to Zerodha/Groww, answers questions like "Am I too exposed to banks?" using broker data and overlap/risk scans. Considered the closest direct competitor.
- **Finapolis** — AI investment companion with persistent context across research, screening, reporting, trading, and monitoring.

### Identified gap (the proposed differentiator)
Very few existing products deeply integrate: geopolitical reasoning, supply-chain effects, company dependency graphs, personalized causal explanations, continuous monitoring with long-term memory, and cross-asset impact analysis (stocks, MFs, ETFs, crypto, commodities). Most current systems still focus on **summarization** rather than **reasoning**.

### Proposed unique architecture — "AI Investment Intelligence Engine"
Rather than "AI Financial Advisor," reframe as an intelligence engine with six layers:
1. **Portfolio Layer** — holdings, transactions, allocation, exposure.
2. **Knowledge Layer** — company relationships, sectors, supply chains, macro indicators (company → suppliers, countries, commodities, currency exposure, sector, competitors).
3. **Intelligence Layer** — financial news, earnings, central bank actions, geopolitical events, social sentiment.
4. **Reasoning Layer** — specialized agents for risk, macro, valuation, portfolio analysis, scenario simulation.
5. **Memory Layer** — investor goals, constraints, historical conversations, preferences.
6. **Advisor Layer** — natural-language explanations, alerts, strategy recommendations.

The critical differentiating piece is a **knowledge graph** maintaining structured relationships (company → suppliers/countries/commodities/currency/sector/competitors), so a geopolitical event can be translated into concrete portfolio impact *before* the LLM generates an explanation.

### Academic literature review (related work)

| Paper | Contribution | Gap remaining |
|---|---|---|
| *Towards Temporal-Aware Multi-Modal RAG in Finance* (MM 2025, Peking University) | FinTMMBench: multimodal corpus (news, prices, tables, charts), temporal retrieval, hybrid multimodal RAG | No explicit causal-chain reasoning between events |
| *Multi-Reranker* (FinanceRAG Challenge, ACM ICAIF 2024) | Optimized finance-specific retrieval/reranking, query expansion, long-context handling | Retrieval-focused only, not portfolio-aware |
| *MultiFinRAG* | Cross-modal retrieval across text/tables/figures/financial statements | No personalized investment reasoning |
| *Bayesian RAG* (Frontiers) | Uncertainty estimation for generated financial answers | Improves reliability, not event reasoning |
| *MMRepAgent* (ScienceDirect) | Automated earnings prediction, news understanding, risk assessment, report generation | Company-centric, not investor-centric |
| *FSFrame* (sparse attention + financial RAG) | Better retrieval, reduced hallucination for financial QA | Still no portfolio reasoning |

**Common pattern across existing work:** News/Question → Retrieve → Generate. No system builds a full pipeline of: News → Entity extraction → Temporal Knowledge Graph → Relationship expansion → Sector impact inference → Portfolio mapping → LLM reasoning → Personalized recommendation.

### Proposed novelty framing (for academic presentation)
Avoid claiming "we introduce knowledge graphs" (not novel by itself). Instead frame as:
> "We propose a Temporal Event Knowledge Graph for portfolio-aware financial reasoning, enabling the AI to model indirect causal relationships between real-world events, financial markets, sectors, and an individual investor's holdings."

Worked example: a geopolitical strike event propagates through the knowledge graph (region instability → oil supply risk → crude oil price ↑ → airlines ↓ / oil producers ↑ → inflation ↑ → interest rates) and is then matched against the user's actual holdings (e.g., Reliance, ONGC, IOC, IndiGo, BPCL) to produce a specific, evidence-backed statement rather than a generic market comment.

---

## 13. Mentor / Investor-Style Assessment (July 2026 feedback)

### Strengths identified
- Correct AI architecture instincts: RAG, orchestration, structured + vector DB separation, contextual prompt assembly, event-driven reasoning, and a correct understanding of narrow ML vs. foundation models vs. fine-tuning — rather than the common beginner mistake of wanting to "train an own AI model."
- Solid systems-level design in the whiteboard architecture: RAG context injection, portfolio serialization into structured JSON before the LLM call, asset-class normalization, delta-sync storage, row-level security, manual ingestion fallback, periodic broker sync.
- Correct MVP boundary: advisory/insights only, no autonomous trade execution — keeps regulatory exposure lower.
- Behavioral coaching angle considered genuinely differentiated, since much of retail investor underperformance is behavioral (panic selling, concentration bias, revenge trading, recency bias) rather than purely informational.

### Key risks flagged, in priority order
1. **Trust** — the platform touches highly sensitive data (bank balances, portfolios, tax info, liabilities, insurance, goals, behavioral patterns); early-stage apps struggle to earn this trust, especially in India. Considered the single biggest bottleneck — above technology, coding, or infrastructure.
2. **Regulation** — any output resembling "sell X, buy Y" enters SEBI investment-advisory territory. Initial product must avoid direct buy/sell instructions, exact allocation directives, guaranteed-return claims, or deterministic advice; stick to insights, simulations, risk explanations, and scenario analysis.
3. **Overbuilding** — the current feature list (aggregation, AI advisor, news intelligence, stress testing, benchmarking, document intelligence, behavioral finance, voice assistant, household management, proprietary LLM) reads like a 50-person startup roadmap, not an MVP.

### Recommended narrowed MVP (mentor's proposed scope)
1. **Portfolio aggregation** — manual entry / CSV upload only; no broker integrations initially (integrations slow development, add compliance overhead, support burden, sync failures, and trust barriers).
2. **AI portfolio understanding** — concentration risk, sector exposure, emergency-fund gaps, diversification analysis, tax awareness, macro exposure, liquidity analysis.
3. **Personalized market/news relevance** — e.g., "RBI rate hike may affect your banking-heavy portfolio."
4. **Daily/weekly AI financial brief** — proposed as a potential signature feature: "Here's what mattered for YOUR portfolio today."

**Explicitly deferred (not for MVP):** proprietary LLM, voice assistant, multi-family hub, real-time sync engine, advanced Monte Carlo, autonomous reasoning agents, complex ML models — considered scale-stage problems, not validation-stage problems.

### Positioning guidance
- Avoid marketing as "AI wealth manager" (regulatory and trust liability).
- Prefer: "intelligent portfolio copilot," "portfolio intelligence layer," "AI-powered financial awareness," "contextual portfolio insights."

### Market assessment
- Real and growing demand in India: rising financial literacy, retail investing growth, SIP culture, younger investors seeking guidance, information overload.
- However, the market does not yet broadly trust "AI financial advisor" positioning — trust, simplicity, clarity, and reliability matter more than flashy AI capability at this stage.

### What investors would likely value vs. worry about
- **Value:** vertical AI angle, India-first positioning, persistent-context approach, long-term B2B/white-label potential (banks, NBFCs, advisors, wealth firms), behavioral-finance direction.
- **Worry:** regulatory exposure, data security, user trust, retention (finance apps are opened less frequently than social apps), LLM hallucination risk in a financial context, and liability if AI-influenced decisions lead to losses.

### Overall verdict (as given)
- Considered a strong, "startup-good" (not just resume-good) idea, realistic only if the MVP scope is drastically narrowed from its current full vision.
- Assessed as demonstrating unusually mature, founder-level thinking (systems, product, infra, AI architecture, business, and compliance) for a student-stage project.
- Recommended framing for a resume/portfolio: emphasize AI systems engineering (RAG-based contextual reasoning, persistent portfolio memory, scalable synchronization pipelines, security-first design) rather than "another chatbot."

---

## 14. Resume / Aim Framing (reference material)

### Sample resume bullet set (detailed version)
- Designed and architected an AI-powered financial portfolio intelligence platform capable of analyzing user investments, assets, liabilities, and market/news data to generate personalized financial insights.
- Built the system architecture for persistent portfolio memory using RAG pipelines, structured PostgreSQL schemas, vector databases, and contextual LLM prompt orchestration.
- Planned real-time portfolio synchronization workflows with broker/banking APIs, background task scheduling, delta-sync logging, and Redis-based caching for scalable market data ingestion.
- Engineered AI reasoning workflows combining portfolio exposure, sector analysis, geopolitical news monitoring, and financial goal tracking to deliver contextual investment suggestions.
- Designed security-first financial infrastructure with OAuth-based integrations, AES-256 encrypted token storage, row-level database security, and audit-ready sync pipelines.
- Proposed advanced AI modules including portfolio stress testing, behavioral finance coaching, tax optimization, Monte Carlo-based goal simulation, and personalized financial alert systems.

### Sample resume bullet set (shortened version)
- Architected an AI-powered portfolio intelligence platform integrating user financial data, live market feeds, and geopolitical news to generate personalized investment insights.
- Designed RAG-based contextual reasoning pipelines using PostgreSQL + vector databases for persistent financial memory and portfolio-aware AI conversations.
- Planned scalable backend workflows for broker API synchronization, real-time market monitoring, portfolio analytics, and AI-driven financial recommendations.
- Incorporated secure financial data handling with OAuth integrations, AES-256 encryption, Redis caching, and role/row-level access control mechanisms.

### Sample "Aim of the Project" framings
**Technical framing:**
- Build an AI-powered financial copilot that provides personalized investment insights by combining a user's complete financial portfolio with real-time market and geopolitical intelligence.
- Develop a unified platform to aggregate and manage diverse financial assets — stocks, mutual funds, bank accounts, fixed deposits, insurance — in a single portfolio view.
- Design a context-aware AI system using RAG that maintains persistent portfolio memory to generate personalized, explainable financial recommendations.
- Implement scalable data ingestion and synchronization pipelines for broker APIs, financial institutions, and live market feeds.
- Empower users to make informed financial decisions through portfolio analysis, risk assessment, asset allocation insights, goal-based planning, and personalized market impact analysis.

**Product/startup framing:**
- Democratize access to intelligent wealth management by building an AI-powered financial advisor tailored for retail investors.
- Transform fragmented financial data into actionable insights using contextual AI reasoning and real-time financial intelligence.
- Deliver personalized financial guidance by combining portfolio context, user goals, market movements, and global news into a unified decision-support system.
- Reduce information overload by automatically identifying events, risks, and opportunities directly relevant to a user's investments.
- Build a secure, scalable, and explainable AI platform capable of serving as a long-term financial copilot rather than a conventional chatbot.

**Recommended balanced version (technical + product):**
- Built an AI-powered financial copilot that combines portfolio data, live market intelligence, and global financial news to generate personalized investment insights.
- Designed a context-aware RAG architecture enabling persistent portfolio memory for explainable AI-driven financial reasoning.
- Developed a scalable portfolio management framework supporting multi-asset aggregation, real-time synchronization, and secure financial data handling.
- Engineered an AI reasoning pipeline for portfolio analytics, risk assessment, asset allocation, and goal-based financial planning.
- Architected the platform with a focus on security, scalability, and explainable AI to support personalized financial decision-making.
