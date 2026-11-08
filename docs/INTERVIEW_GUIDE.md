# Interview guide

## 30-second pitch

I built a delivery analytics copilot over a reproducible shipment dataset. It turns a business question into a validated analysis, executes read-only SQL, and shows the evidence and quality checks behind the answer. A deterministic planner makes the demo usable without credentials. An optional LLM planner uses the same tools. I built a 50-case benchmark against independent CSV calculations so I could measure accuracy, grounding and safety together.

## Two-minute technical explanation

The project has three paths. Offline, Python generates a fixed-seed versioned snapshot and builds a normalized SQLite database with foreign keys. Online, React sends a question to FastAPI. A LangGraph workflow interprets the question, validates the intent and reporting periods, fetches the KPI rule, runs approved SQLite queries and reconciles the evidence. The frontend consumes newline-delimited events, then renders the answer, chart, SQL and quality results.

The important decision was to restrict the planner's authority. It emits a typed plan, and application code chooses a fixed SQL template. Parameters are validated and bound, and SQLite opens read-only with an authorizer and query bounds. The model never needs the rows or access to the database. Demo mode uses documented patterns and shares the same execution and verification paths.

For evaluation, I hand-labeled the expected scope of each benchmark case and calculated reference outputs directly from CSV in Python. This caught plan errors as well as arithmetic and evidence errors. The versioned benchmark and single-container build make the demo reproducible.

## Walk through the May request

1. FastAPI validates the body and assigns a request ID.
2. The planner chooses a category driver investigation over April and May 2026.
3. The graph retrieves the on-time rule and runs monthly KPI, category and quality queries.
4. The verifier checks that on-time plus late equals valid, that query counts match the quality cohort, and that category counts reconcile with the monthly totals.
5. SQL returned 940 and 910 on-time shipments out of 1,000 each. Safety & Control had 39 late shipments in May versus 12 in April. Its within-category deterioration and larger shipment share together added 2.70 points to the overall late rate.
6. The browser renders the verified summary, category chart, exclusions and executed queries.

## Ten likely questions

1. **Why LangGraph?** Its explicit nodes and conditional edges make the state transitions inspectable. The team can see whether an investigation stopped during validation, execution or verification.
2. **Why constrain SQL?** A business analytics agent only needs a small vocabulary of read operations. A registry, validated bindings and a database authorizer keep authority limited even if the planner is tricked.
3. **Why have a deterministic demo?** It runs without external credentials or model variability. It also gives a stable baseline to compare against the LLM planner.
4. **What makes it agentic?** It selects an analysis recipe, calls tools and verifies their outputs before answering. Different intents take different data paths and failures stop downstream work.
5. **What defines an on-time delivery?** A valid completed shipment arriving at or before its promise. Promise month anchors the cohort, so a late arrival that crosses a month boundary still counts against the original promise.
6. **How did you verify the KPI?** I checked the controlled results with independent SQL, and the benchmark recalculates expected counts and rates directly from CSV using Python.
7. **How do you explain category drivers?** Count changes identify extra late shipments. Dividing each category's late shipments by total valid shipments attributes changes in the overall late rate. A symmetric split shows the rate and mix effects.
8. **What does groundedness mean here?** Structured values and chart data reconcile with executed query rows and independent truth. Findings refer to query evidence. The scorer does not claim to grade every possible free-form sentence.
9. **How do you handle provider failures?** Validate model output, bound time and tokens, cap concurrent calls, and return a safe failure with the remaining steps skipped. Demo mode can still run.
10. **What would change for real operations?** Add source reconciliation, authenticated data access, dataset isolation, fresh ingestion, unseen evaluation questions and monitoring. Add operational exception data before making causal claims.

## Trade-offs and challenges

- Fixed templates keep security and auditability straightforward. New metrics or dimensions need application changes and benchmark coverage.
- Streaming improves trace visibility and adds client-side framing and cancellation handling. The browser test exercises the same API used by the dashboard.
- A finite simulated snapshot makes regression tests reproducible. It cannot validate how the application handles live source quality or forecast future performance.
- Category shipment volumes changed between April and May. The contribution arithmetic addresses that by using overall period denominators and decomposing volume mix and within-category rates.
- Host tool differences surfaced during verification. pnpm replaced npm on this workstation. Tests ran with the installed Edge browser. The Linux Docker image independently exercised dependency installation and production asset serving.
