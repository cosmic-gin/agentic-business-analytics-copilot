# Agent workflow

LangGraph compiles a typed state machine. Each node returns an update, which the graph merges into the current investigation state. State holds the question, plan, query IDs, tool results, comparison, quality, verification outcome and trace. A node failure routes to the end and marks downstream work skipped.

| Node | Role |
| --- | --- |
| Interpret | Apply the question guard and invoke the selected planner |
| Validate | Check supported intent, dates and dimension combinations |
| Definition | Load the KPI definition from YAML |
| Plan | Map the structured intent to a bounded query recipe |
| Select | Check the recipe against the approved analytics tools |
| Execute | Run monthly, comparison or breakdown queries |
| Quality | Count valid and excluded rows over the same date window |
| Verify | Recompute the KPI ratios from returned counts and reconcile category and quality totals |
| Answer | Render structured findings and chart data using verified evidence |

The quality-only workflow skips the primary query step and runs the quality query. Other successful analyses execute at most two primary queries and one quality query. The browser shows running and terminal states from the stream. Rejected, ambiguous and unsupported questions leave the SQL and answer steps skipped. Verification failures suppress unverified comparisons, drivers and charts. The API can still return raw evidence for diagnosis.

## Deterministic patterns

| Intent | Example | Defaults |
| --- | --- | --- |
| Monthly KPI | What was the on-time delivery rate in May? | Ask for a month unless the question explicitly requests the latest |
| Comparison | Compare April and May on-time delivery | Sort the months chronologically. A single comparison month uses the previous month |
| Drivers | Why did delivery performance drop in May? | Compare to previous month and break down by category. An omitted month uses the latest |
| Trend | Show the monthly on-time delivery trend | Full snapshot. Two named months form an inclusive window |
| Breakdown | Which carrier performs worst? | Latest month when omitted. Carrier and warehouse performance default to late rate |
| Quality | Are incomplete records affecting the KPI in October? | Latest month when omitted. Two months form an inclusive window |

Use one breakdown dimension per question. Categories default to late counts where the question specifies no rate or volume. Single-order tracking, forecasts, sales and root-cause questions require data or tools beyond the demo's scope.

## Optional model planning

OpenAI and Groq return a structured plan with an intent, metric, dates, ranking dimension and optional member IDs. The model sees the question, snapshot coverage and a catalog of permitted category, carrier and warehouse names. The backend binds only allowlisted IDs supported by the question. Use a member's full catalog name when asking for a filtered cohort.

The planner preserves an explicitly requested KPI and orders comparison periods chronologically. If the question names a single comparison month and the model repeats it, the planner uses the preceding month as the baseline. A monthly KPI with no named month or explicit request for the latest period needs clarification.

OpenAI uses Responses structured output. Groq uses Chat Completions structured output and low reasoning effort for its default model. Groq uses string enums for optional plan fields. The adapter normalizes them before the shared planner validates the SQL bindings. The app uses one provider request, zero retries and a 10-second SDK timeout. Output caps are 350 tokens for OpenAI and 1,200 for Groq, where the budget includes reasoning. Each process permits at most two concurrent provider calls. Usage is visible in the investigation result, and cost estimates require both rates for the selected provider.

Validation and database permissions remain in application code. The application exposes no arbitrary SQL tool. The SQLite authorizer rejects writes, schema reads, extension loading, PRAGMAs and attachments. Structured logs omit question text, credentials and provider error bodies. [OpenAI Docs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses) · [Groq structured outputs](https://console.groq.com/docs/structured-outputs)
