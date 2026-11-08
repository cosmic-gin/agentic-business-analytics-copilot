# Phase log

## PHASE 0 COMPLETED

- What we built — architecture, contracts, roadmap and workspace conventions.
- Why we built it — separate ingestion, planning, analytics and presentation before implementation.
- Important files — AGENTS.md, docs/PROJECT_PLAN.md and docs/PROGRESS.md.
- How components work together — React calls FastAPI, which runs a LangGraph workflow over a constrained SQLite reader.
- Commands and results — directory and Git inspection confirmed an empty workspace without Git metadata. Python, Node, Git, uv and Docker CLI version checks worked. npm was absent from PATH.
- How to verify — read PROJECT_PLAN.md and run the version commands locally.
- Concepts — component boundaries, typed contracts, deterministic execution, least privilege.
- Interview explanation — the model can choose an analysis, while application code owns data access and claims.
- Next — start the FastAPI and React shells and verify their connection.

## PHASE 1 COMPLETED

- What we built — FastAPI health route, request IDs, environment settings, CORS, React shell and dependency locks.
- Why we built it — prove both runtimes work before adding analytics.
- Important files — pyproject.toml, uv.lock, backend/app/main.py, frontend/vite.config.ts and pnpm-lock.yaml.
- How components work together — React requests /api/health, Vite proxies it to FastAPI, and React renders the response or a connection error.
- Commands and results — uv sync, pytest (1 passed), pnpm install and pnpm build (success). Windows sandbox path restrictions required running the build outside the sandbox. Browser rendering scheduled with the dashboard.
- How to verify — follow README and open /api/health and the Vite page.
- Concepts — request-response cycle, proxy, CORS, environment configuration and lockfiles.
- Interview explanation — relative API routes work under the dev proxy and the same-origin production server.
- Next — create and independently verify the simulated dataset.

## PHASE 2 COMPLETED

- What we built — fixed-seed data generator, versioned CSVs, SQLite builder, data dictionary and KPI definitions.
- Why we built it — make the business investigation repeatable and auditable.
- Important files — scripts/generate_snapshot.py, scripts/build_database.py, schema.sql, data/metadata and test_snapshot.py.
- How components work together — CSV loads into normalized tables with foreign keys. Promised month assigns cohorts and valid completed records determine rates.
- Commands and results — python -m scripts.generate_snapshot, python -m scripts.build_database and pytest -q -s. Three passed. Direct SQL returned 940/1000 in April and 910/1000 in May. Safety & Control added 27 late deliveries. The rebuild matched byte-for-byte on this host.
- How to verify — run pytest -s backend/tests/test_snapshot.py to see the independent SQL results.
- Concepts — reporting cohorts, denominator policy, referential integrity, reproducible fixtures.
- Interview explanation — a precise denominator lets analysts compare months without silently changing who counts.
- Next — implement typed, parameterized read-only tools.

## PHASE 3 COMPLETED

- What we built — typed scopes, KPI tools, SQL evidence, SQLite authorizer and category contribution arithmetic.
- Why we built it — allow useful investigation without giving a planner unrestricted database access.
- Important files — db/reader.py, db/queries.py, services/analytics.py, schemas/analytics.py and test_analytics.py.
- How components work together — validated filters bind to fixed SQL. A read-only connection enforces table and operation restrictions and returns capped evidence.
- Commands and results — ruff check backend scripts passed. pytest -q -p no:cacheprovider passed 21 tests including injection inputs, corrupted files, empty scopes and forbidden SQL.
- How to verify — run pytest backend/tests/test_analytics.py.
- Concepts — parameters are data, read-only flags and authorization narrow access, and contribution accounts for both volume and rate.
- Interview explanation — rank by late count to describe volume. Divide each category's late count by overall volume to measure how it contributes to the overall rate.
- Next — orchestrate the tools with LangGraph and add an optional provider.

## PHASE 4 COMPLETED

- What we built — typed LangGraph state and nine nodes, two planners, live step events and deterministic answer rendering.
- Why we built it — make each investigation inspectable and keep generated plans separate from numerical claims.
- Important files — backend/app/agent/{planning,providers,nodes,state,graph,answer}.py and test_agent.py.
- How components work together — guard and validate a typed intent, execute approved SQL, reconcile evidence against the quality cohort, then assemble the response.
- Commands and results — Ruff cleaned three import groups. Pytest passed 28 tests, including the May graph, zero-query unsafe exits and malformed provider output.
- How to verify — run pytest backend/tests/test_agent.py. Inspect events emitted by AnalyticsAgent.stream.
- Concepts — graph state, conditional routing, structured output, evidence reconciliation and bounded provider calls.
- Interview explanation — the system chooses and verifies database tools in a traceable sequence. The narrative reads verified results.
- Next — expose the graph through REST and NDJSON.
- Reference — [OpenAI Docs for Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses).

## PHASE 5 COMPLETED

- What we built — six REST endpoints, streamed steps, OpenAPI, request IDs, response-safe error handling and a 4096-byte body cap.
- Why we built it — allow the UI to display actual progress and trace each investigation.
- Important files — backend/app/api/routes.py, schemas/api.py, main.py and test_health.py.
- How components work together — the API validates payloads and resolves the requested mode before invoking a shared graph.
- Commands and results — Ruff passed and pytest passed 37 tests. REST and streaming matched on the May result, and an oversized body returned 413.
- How to verify — open /docs or POST to /api/ask after starting uvicorn.
- Concepts — REST, stream framing, middleware, request correlation and transport versus business statuses.
- Interview explanation — ambiguous questions have valid HTTP responses with an analysis status. Invalid request fields use HTTP 422.
- Next — build the dashboard around these contracts.

## PHASE 6 COMPLETED

- What we built — React dashboard, API-backed overview and examples, live trace, findings, charts, quality, SQL and a benchmark view.
- Why we built it — make the evidence visible to a business user without needing a SQL client.
- Important files — frontend/src/pages, components, hooks, services/api.ts and tests/dashboard.spec.ts.
- How components work together — the fetch reader parses NDJSON lines and updates React state. Recharts consumes only the returned chart rows. The evaluation view handles a missing report.
- Commands and results — pnpm lint, typecheck and build passed. Three headless Edge tests passed after narrowing a SQL locator that matched two templates.
- How to verify — run pnpm dev and use the May example. Expand monthly_kpi and inspect parameters.
- Concepts — streaming updates, controlled form state, typed chart data, and user-visible error states.
- Interview explanation — progress is emitted by the running workflow, so a refused question displays skipped downstream steps.
- Next — implement the independent benchmark and generate its report.

## PHASE 7 COMPLETED

- What we built — versioned benchmark, independent Python CSV reference, CLI scorer and dashboard report.
- Why we built it — measure whether answers are correct, supported by evidence and within permissions.
- Important files — evals/benchmark-v1.jsonl, evals/reference.py, evals/run.py, evals/reports/demo-v1.json and docs/EVALUATION.md.
- How components work together — benchmark expectations specify scope. The reference computes independent truth, then compares it with the graph result and its evidence.
- Commands and results — python -m evals.run passed 50/50. Accuracy, SQL execution and groundedness were 36/36 each. Unsafe rejection was 6/6. Median 23.78 ms, p95 64.03 ms. Pytest passed 38 tests.
- How to verify — run the CLI and click Evaluation in the sidebar.
- Concepts — independent ground truth, applicability, tolerance, percentiles and deterministic evidence grading.
- Interview explanation — a correct number alone cannot show that an approved query ran or that a malicious request was refused.
- Next — expand failure, security and browser coverage.

## PHASE 8 COMPLETED

- What we built — evidence failure checks, provider error and cost tests, read-only readiness probe, log redaction checks and mobile and evaluation browser coverage.
- Why we built it — test the risks at each layer instead of relying on a successful demo.
- Important files — backend/tests/test_hardening.py, frontend/tests/evaluation.spec.ts and frontend/pnpm-workspace.yaml.
- How components work together — SQL and quality rows reconcile before conclusions are returned. The provider uses bounded concurrent calls, time and token caps. The build consumes browser-safe config.
- Commands and results — Ruff and pytest passed (43). pnpm lint and build passed, including TypeScript. Five Edge tests passed. Ripgrep confirmed a build-time secret canary was absent. pip-audit and pnpm audit reported no known vulnerabilities. The npm audit initially found a moderate minimatch issue. An override to 11.0.1 fixed it and ESLint still passed.
- How to verify — run pytest and pnpm test. Test the unsafe input and inspect the skipped steps.
- Concepts — defense in depth, readiness probes, secret canaries, provider doubles, audit remediation.
- Interview explanation — a malformed plan or inconsistent result fails closed before producing a business explanation.
- Next — build and smoke test a single non-root container.

## PHASE 9 COMPLETED

- What we built — multi-stage Docker image, Compose, Render Blueprint, environment example, production assets and GitHub Actions.
- Why we built it — serve the dashboard and API from one repeatable deployment artifact.
- Important files — Dockerfile, .dockerignore, docker-compose.yml, render.yaml, .env.example and .github/workflows/ci.yml.
- How components work together — Node compiles React in the build stage. The Python runtime reconstructs SQLite from CSV and serves the API and assets from one port.
- Commands and results — Docker Desktop started successfully. docker compose config --quiet and YAML parsing passed. docker build succeeded. A temporary container ran as UID 10001 with a read-only root filesystem and a custom PORT. Health, index, JS asset, May evidence, evaluation and unsafe request checks all passed. The before and after database hashes matched. Five Edge tests also passed against FastAPI serving the production bundle.
- How to verify — docker compose up --build and open http://127.0.0.1:8000.
- Concepts — multi-stage images, build versus runtime, port binding, immutable assets and non-root execution.
- Interview explanation — build-time data makes the demo independent of hosted storage and credentials.
- Next — capture screenshots and finish the portfolio and interview guides. CI and Render are configured for future use.

## PHASE 10 COMPLETED

- What we built — portfolio README, architecture and workflow guides, data design, benchmark guide, interview Q&A, five-minute demo and screenshots from the local Docker build.
- Why we built it — let a reviewer run, understand and audit the project without needing a live presentation.
- Important files — README.md, docs/ARCHITECTURE.md, docs/AGENT_WORKFLOW.md, docs/DATABASE_DESIGN.md, docs/EVALUATION.md, docs/INTERVIEW_GUIDE.md, docs/DEMO_SCRIPT.md and docs/screenshots.
- How components work together — the README connects setup and screenshots to the same query, data and benchmark artifacts served by the running image.
- Commands and results — Ruff passed. Pytest passed 45 tests. The final versioned benchmark passed 50/50 with p50 9.36 ms and p95 25.43 ms. Local Markdown link checks passed. The Docker image rebuilt and passed final Edge acceptance for the exact May question, SQL and quality evidence, the delete request and the evaluation page. The SQLite hash was unchanged. Final QA also covered the natural-language word “drop” and clearer rounding in rate attribution.
- How to verify — run docker compose up --build, follow the demo script and compare the UI with the screenshots.
- Concepts — reproducible demonstrations, independent evidence, explicit limits and interview framing.
- Interview explanation — walk through the May question and show how validation, read-only SQL, data quality and evidence checks produce the answer.
- Next — use the interview guide for rehearsal. Live OpenAI verification needs credentials. Hosted CI and public deployment remain future actions.

## PHASE 11 COMPLETED

- What we built — a release guide, a reusable HTTP smoke check, and a local Git index ready for review.
- Why we built it — verify the exact release path before creating a GitHub repository or deploying.
- Important files — docs/RELEASE_GUIDE.md, scripts/smoke_test.py, .github/workflows/ci.yml and render.yaml.
- How components work together — the smoke script checks production assets and API results locally, in GitHub Actions and against an optional hosted URL. The container job compares SQLite hashes around the smoke run.
- Commands and results — 45 backend tests, five production Edge tests and 50/50 benchmark cases passed. Ruff, frontend lint, type checking, production build, actionlint and Render JSON Schema validation passed. Both lockfile audits reported no known vulnerabilities. Docker Compose reached healthy, passed all ten smoke checks and preserved the database hash.
- How to verify — follow docs/RELEASE_GUIDE.md from the Compose launch through the staged Git review.
- Concepts — readiness versus smoke testing, a checked Git index, release gates and manual deployment.
- Interview explanation — the same smoke commands check the artifact end to end before and after publication.
- Next — configure the author's Git identity and create the first commit locally. Remote publication, hosted CI, Render deployment and credentialed OpenAI testing remain separate actions.

## PHASE 12 IMPLEMENTED

- What we built — OpenAI and Groq adapters, validated named filters, provider usage in the dashboard, a private LLM Compose override and a six-case LLM benchmark.
- Why we built it — make model-backed interpretation available with either OpenAI or a free-tier Groq key, and distinguish live LLM results from demo results.
- Important files — backend/app/agent/providers.py, docker-compose.llm.yml, evals/benchmark-llm-v1.jsonl, scripts/smoke_test.py and docs/RELEASE_GUIDE.md.
- How components work together — the provider chooses a typed plan using a catalog. Application code validates its scope, binds filters and verifies the SQLite result. The dashboard surfaces the model, usage and the matching benchmark report.
- Commands and results — Ruff and 54 backend tests passed. Both SDK paths passed with simulated HTTP responses. Six production Edge tests passed. The demo benchmark passed 50/50. The LLM scorer passed its six scripted-provider cases. The Docker demo passed all ten smoke checks and preserved the SQLite hash. The private LLM override started with a test-only key and rejected an unsafe request before any provider call.
- How to verify — configure a Groq or OpenAI key locally, run the private Compose override and execute the LLM smoke and benchmark commands in the release guide.
- Concepts — constrained model outputs, provider adapters, scoped cohort validation, provenance and independent evaluation.
- Interview explanation — the model interprets a broader range of questions and can pick a named cohort. The SQL registry and evidence checks still determine the answer.
- Next — run the authenticated LLM smoke and live evaluation. The workspace has no configured provider credentials. GitHub publication and hosted deployment remain subject to approval.

## PHASE 13 DEPLOYMENT READY

- What we built — public demo and protected Groq Free Plan hosting profiles, a shared password gate, CI container verification and a step-by-step Render guide.
- Why we built it — share a hosted portfolio app while limiting access to the provider-backed service.
- Important files — render.yaml, render.llm.yaml, backend/app/main.py, scripts/smoke_test.py and docs/RELEASE_GUIDE.md.
- How components work together — Render supplies the provider key, generates a separate workspace password and probes SQLite readiness. The web app challenges anonymous visitors before processing provider requests.
- Commands and results — Ruff, 57 backend tests and the 50/50 demo benchmark passed. Both Blueprints conformed to Render's published schema. Actionlint passed. Both Docker profiles passed smoke tests under a 512 MiB cap at PORT 10000 and preserved the SQLite hash. Edge authenticated to the protected container and displayed streamed SQL evidence in demo mode. Authenticated SDK integration tests covered model planning with simulated HTTP responses.
- How to verify — choose the Blueprint in the release guide, deploy after approving publication, and run the matching smoke command against the hosted HTTPS URL.
- Concepts — runtime secrets, readiness, authenticated deployment, static build artifacts and external verification.
- Interview explanation — the same image can run an open deterministic demo or a password-protected provider-backed workspace through environment settings.
- Next — configure a real provider key for live verification. Hosted GitHub Actions and Render verification require an approved publication and deploy.

## PHASE 14 LIVE LLM VERIFICATION COMPLETED

- What we built — a Groq wire schema compatible with observed provider output, KPI and reporting-period normalization, and live verification of the protected deployment image.
- Why we built it — confirm actual provider behavior and correct analysis outcomes with a configured key.
- Important files — backend/app/agent/providers.py, backend/app/agent/planning.py, backend/tests/test_llm_integration.py, render.llm.yaml and docs/screenshots/llm-investigation.png.
- How components work together — the model proposes a structured analysis. The adapter normalizes provider fields and explicit business rules. SQLite calculates and verifies the result.
- Commands and results — Ruff, 62 backend tests, six production browser regression tests and 50/50 demo cases passed. The first Groq 20B run passed 48/56. The 120B run passed 54/56, including all six LLM-specific cases and all seven adversarial cases. Both comparison misses passed a separate live replay after the final correction. The final image passed protected smoke and live Edge verification, preserved the SQLite hash, and displayed the 56-case report. Both Render Blueprints passed schema validation.
- How to verify — start the private Compose profile, run the live smoke test, and try Safety & Control in May. The response should show Groq usage and 201 of 240 shipments on time.
- Concepts — provider-specific structured output, deterministic safeguards, benchmark replay and deployment parity.
- Interview explanation — live evaluation uncovered schema and scope variations. The system now checks explicit metric wording and dates before it runs allowlisted queries.
- Next — prepare the first local release commit, then publish and run the hosted smoke test after approval.

## PHASE 15 FIRST RELEASE PREPARED

- What we built — a Docker quick start in the README, GitHub attribution checks and a publishing and hosting walkthrough.
- Important files — README.md, docs/RELEASE_GUIDE.md, render.yaml and render.llm.yaml.
- Commands and results — the normal LLM Compose entry point reached healthy and all live smoke checks passed. The response reported real provider token usage, April at 94%, May at 91% and 201 of 240 shipments on time for the named category. Unsafe requests stopped before the provider and SQL. Ruff and 62 backend tests passed. Frontend lint, type checking and production build passed.
- Next — after approval, publish the main branch, check attribution and CI on GitHub, and deploy and verify the chosen Render profile.
