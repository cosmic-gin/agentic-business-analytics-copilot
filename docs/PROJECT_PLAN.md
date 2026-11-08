# Project plan

Build a delivery analytics dashboard over a versioned simulated snapshot. React owns request state and renders evidence. FastAPI validates input, emits request IDs and serves compiled assets. LangGraph coordinates deterministic or model-backed planning, approved tools, quality checks, evidence verification and grounded answer rendering. An offline builder ingests CSV into SQLite. Runtime readers use read-only connections and a fixed query registry. The evaluation CLI reads CSV independently and writes reports by mode. A single container serves both tiers.

## Contracts

| Endpoint | Contract |
| --- | --- |
| GET /api/health | Health and API version |
| GET /api/metadata | Dataset metadata, current overview, enabled modes |
| GET /api/kpis | KPI definitions |
| GET /api/examples | Supported example questions |
| POST /api/ask | AskRequest with question and optional mode. AnalysisResponse with status, summary, comparison, findings, evidence, chart, SQL, quality, caveats, steps and execution metadata |
| POST /api/ask/stream | Same request. NDJSON step events followed by result or error |
| GET /api/evaluations | Versioned benchmark report or explicit unavailable state |

Major types include AskRequest, Plan, QueryEvidence, WorkflowStep, Finding, AnalysisResponse and EvaluationReport. The unversioned routes are the v1 compatibility surface. Breaking versions use a new path.

## Scope and trade-offs

Support on-time and late delivery KPIs, month comparisons, trends, category drivers, carrier and warehouse breakdowns, and quality checks. Month uses promised date in UTC. Only valid completed rows enter the denominator. Unqualified rankings use the latest completed snapshot month. Unsupported requests return guidance. Demo planning uses documented patterns. LLM planning converts a question into a constrained plan. Both use the same query registry and deterministic narrative renderer. SQLite simplifies reproduction and deployment for this single-tenant snapshot. Explanations separate count changes, rate changes and mix. They describe observed associations.

## Roadmap and acceptance

| Phase | Acceptance |
| --- | --- |
| 0 | Inspect tooling, document architecture and contracts |
| 1 | Health endpoint responds and React builds |
| 2 | Versioned snapshot rebuilds and SQL verifies controlled KPIs |
| 3 | Typed tools, validated parameters, authorization and independent checks |
| 4 | Graph runs real queries, verifies evidence and handles unsafe requests |
| 5 | API contracts tested, request bounds and tracing enforced |
| 6 | Responsive dashboard renders real streamed progress and evidence |
| 7 | 50-case benchmark runs against independent CSV expectations |
| 8 | Full integration, lint, typing, safety and browser checks |
| 9 | Single-image and Render configuration verified to environment limits |
| 10 | Setup, diagrams, demo, screenshots and interview materials verified |

References: [LangGraph](https://docs.langchain.com/oss/python/langgraph/graph-api), [Vite](https://vite.dev/guide/), [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [Render](https://render.com/docs/blueprint-spec).
