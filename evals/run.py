import argparse
from collections import defaultdict
from datetime import datetime, timezone
from math import ceil, isclose, isfinite
from pathlib import Path
from statistics import mean
from time import perf_counter, sleep

from backend.app.agent.graph import AnalyticsAgent
from backend.app.agent.planning import DeterministicPlanner
from backend.app.agent.providers import build_llm_planner
from backend.app.core.config import Settings
from backend.app.schemas.api import EvaluationCase, EvaluationMetric, EvaluationReport
from backend.app.services.analytics import AnalyticsTools
from evals.reference import ROOT, Case, Reference

VERSION = "v1"
BENCHMARK = ROOT / "evals/benchmark-v1.jsonl"
LLM_BENCHMARK = ROOT / "evals/benchmark-llm-v1.jsonl"
REPORT = ROOT / "evals/reports/demo-v1.json"
FILTER_KEYS = ("category_id", "warehouse_id", "carrier_id")


def matches(actual, expected) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(key in actual and matches(actual[key], value)
                                                 for key, value in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(
            matches(a, b) for a, b in zip(actual, expected, strict=True)
        )
    if isinstance(expected, float):
        return isinstance(actual, (int, float)) and isclose(actual, expected, rel_tol=0, abs_tol=1e-7)
    return actual == expected


def grade_answer(result, case: Case, reference: Reference):
    dimension = case.dimension
    primary, quality = reference.query_rows(case, dimension)
    evidence = {"data_quality": [quality]}
    if case.intent != "quality":
        evidence = {f"{dimension}_breakdown" if dimension else "monthly_kpi": primary, **evidence}
    category_rows = []
    if case.intent == "drivers":
        category_rows, _ = reference.query_rows(case, "category")
        evidence["category_breakdown"] = category_rows

    actual_queries = {query.query_id: query for query in result.sql_evidence}
    sql = len(result.sql_evidence) == len(evidence) and set(actual_queries) == set(evidence) and all(
        query.status == "ok" and query.row_count == len(query.rows)
        and query.parameters.get("start") == case.start and query.parameters.get("end") == case.end
        and query.parameters.get("cutoff") == reference.manifest["cutoff_exclusive"]
        and all(query.parameters.get(key) == case.filters.get(key) for key in FILTER_KEYS)
        and query.sql.strip().upper().startswith("SELECT ")
        for query in result.sql_evidence
    )
    exact_rows = sql and all(matches(actual_queries[key].rows, rows) for key, rows in evidence.items())
    plan = result.plan
    valid_plan = bool(plan and (plan.intent, plan.scope.start, plan.scope.end, plan.dimension) ==
                      (case.intent, case.start, case.end, dimension))
    if plan:
        valid_plan = valid_plan and all(getattr(plan.scope, key) == case.filters.get(key) for key in FILTER_KEYS)
    if plan and case.intent != "quality":
        valid_plan = valid_plan and plan.metric == case.metric
    if plan and dimension:
        valid_plan = valid_plan and plan.ranking == case.ranking

    records, valid = quality["records"], quality["valid_deliveries"]
    quality_expected = {**quality, "excluded": records - valid,
                        "completeness_pct": 100 * valid / records if records else None}
    numeric = bool(valid_plan and result.data_quality and matches(result.data_quality.model_dump(), quality_expected))
    if case.intent == "quality":
        grounded = bool(exact_rows and matches(result.supporting_evidence, [quality]) and not result.chart_data)
        return numeric, sql, grounded

    summary = result.summary
    shown = primary
    chart_rows = primary
    chart_series = {case.metric}
    chart_key = "name" if dimension else "period"
    chart_kind = "bar" if dimension or len(primary) == 1 else "line"
    chart_unit = "percent" if case.metric.endswith("_rate") else "count"
    if case.intent in {"compare", "drivers"}:
        endpoints = {case.start, case.end}
        shown = [row for row in primary if row["period"] in endpoints]
        before, after = shown
        rate_change = after[case.metric] - before[case.metric] if chart_unit == "percent" else None
        expected = dict(previous_period=case.start, current_period=case.end,
                        previous_value=before[case.metric], current_value=after[case.metric],
                        previous_valid=before["valid_deliveries"], current_valid=after["valid_deliveries"],
                        previous_late=before["late_deliveries"], current_late=after["late_deliveries"],
                        change_pp=rate_change)
        numeric = bool(numeric and result.kpi_comparison and matches(result.kpi_comparison.model_dump(), expected))
        if chart_unit == "percent":
            numeric = numeric and all(f"{row[case.metric]:.2f}%" in summary for row in shown)
        chart_rows = shown
        if case.intent == "drivers":
            grouped = {(row["period"], row["name"]): row for row in category_rows}
            expected_drivers = []
            for name in sorted({row["name"] for row in category_rows}):
                first, second = grouped[(case.start, name)], grouped[(case.end, name)]
                late_before, late_after = first["late_deliveries"], second["late_deliveries"]
                expected_drivers.append(dict(category=name, previous_late=late_before, current_late=late_after,
                    late_count_change=late_after - late_before, previous_valid=first["valid_deliveries"],
                    current_valid=second["valid_deliveries"], previous_late_rate=first["late_rate"],
                    current_late_rate=second["late_rate"], late_rate_contribution_pp=100 * (
                        late_after / after["valid_deliveries"] - late_before / before["valid_deliveries"]
                    )))
            expected_drivers.sort(key=lambda row: (-row["late_count_change"], row["category"]))
            numeric = numeric and matches([driver.model_dump() for driver in result.drivers], expected_drivers)
            winner = expected_drivers[0]
            if winner["late_count_change"] > 0:
                numeric = numeric and winner["category"] in summary and f'+{winner["late_count_change"]}' in summary
            chart_rows = [{"category": row["category"], "before": row["previous_late"],
                           "after": row["current_late"]} for row in expected_drivers]
            chart_series, chart_key, chart_kind, chart_unit = {"before", "after"}, "category", "bar", "count"
    elif dimension:
        extreme = (min if case.ranking == "lowest" else max)(row[case.metric] for row in primary)
        numeric = numeric and all(row["name"] in summary for row in primary if row[case.metric] == extreme)

    numeric = numeric and matches(result.supporting_evidence, shown)
    chart = result.chart_data
    chart_matches = bool(chart and chart.x_key == chart_key and chart.kind == chart_kind and chart.unit == chart_unit
                         and set(chart.series) == chart_series and matches(chart.rows, chart_rows))
    grounded = bool(exact_rows and chart_matches and numeric and all(
        finding.evidence_ids and set(finding.evidence_ids) <= actual_queries.keys()
        for finding in result.findings
    ))
    return numeric, sql, grounded


def evaluate_case(agent, case, reference):
    started = perf_counter()
    reasons = []
    numeric = sql = grounded = unsafe = cost = None
    try:
        result = agent.ask(case.question)
        actual = result.status
        if actual != case.status:
            reasons.append(f"Expected {case.status}, received {actual}.")
        if case.status == "ok":
            numeric, sql, grounded = grade_answer(result, case, reference) if actual == "ok" else (False, False, False)
            if not numeric:
                reasons.append("Numeric output or scope differs from independent CSV reference.")
            if not sql:
                reasons.append("Expected scoped queries did not all execute.")
            if not grounded:
                reasons.append("Evidence, chart or structured claims did not reconcile.")
        elif result.sql_evidence:
            reasons.append("A non-analytical case executed SQL.")
        if case.status == "rejected":
            unsafe = actual == "rejected" and not result.sql_evidence
        usage = result.execution_metadata.provider_usage
        if usage:
            cost = usage.estimated_cost_usd
        if agent.mode == "llm" and case.status == "ok" and (
            not usage or usage.input_tokens <= 0 or usage.output_tokens <= 0
        ):
            reasons.append("Expected provider token usage for an LLM investigation.")
    except Exception as error:
        actual = "error"
        reasons.append(f"Runner error ({type(error).__name__}).")
        if case.status == "ok":
            numeric = sql = grounded = False
        if case.status == "rejected":
            unsafe = False
    return EvaluationCase(
        id=case.id, category=case.category, question=case.question, expected_status=case.status,
        actual_status=actual, passed=not reasons, numeric_match=numeric, sql_success=sql,
        grounded=grounded, unsafe_rejected=unsafe, elapsed_ms=round((perf_counter() - started) * 1000, 2),
        estimated_cost_usd=cost, failure_reasons=reasons,
    )


def metric(values):
    relevant = [value for value in values if value is not None]
    passed = sum(relevant)
    return EvaluationMetric(passed=passed, total=len(relevant), rate=passed / len(relevant) if relevant else None)


def run_benchmark(agent, *, suite="full", delay_seconds=0, provider=None, model=None):
    reference = Reference()
    sources = [BENCHMARK] if suite == "full" else []
    if agent.mode == "llm":
        sources.append(LLM_BENCHMARK)
    benchmark = [Case.model_validate_json(line) for source in sources
                 for line in source.read_text(encoding="utf-8").splitlines()]
    results = []
    for case in benchmark:
        if results and delay_seconds:
            sleep(delay_seconds)
        results.append(evaluate_case(agent, case, reference))
    categories = defaultdict(list)
    for case in results:
        categories[case.category].append(case.passed)
    latencies = sorted(case.elapsed_ms for case in results)
    costs = [case.estimated_cost_usd for case in results if case.estimated_cost_usd is not None]
    return EvaluationReport(
        benchmark_version=f"{VERSION}-llm-{suite}" if agent.mode == "llm" else VERSION,
        dataset_version=reference.manifest["version"], mode=agent.mode, provider=provider, model=model,
        generated_at=datetime.now(timezone.utc).isoformat(),
        overall=metric(case.passed for case in results),
        numeric_accuracy=metric(case.numeric_match for case in results),
        sql_success=metric(case.sql_success for case in results),
        groundedness=metric(case.grounded for case in results),
        unsafe_rejection=metric(case.unsafe_rejected for case in results),
        latency_ms={"p50": latencies[ceil(len(latencies) * 0.5) - 1],
                    "p95": latencies[ceil(len(latencies) * 0.95) - 1], "max": latencies[-1]},
        average_cost_usd=mean(costs) if costs else None,
        cost_status="measured" if costs else "not_applicable" if agent.mode == "demo" else "unavailable",
        categories={name: metric(values) for name, values in categories.items()}, cases=results,
    )


def main():
    parser = argparse.ArgumentParser(description="Evaluate the delivery analytics agent.")
    parser.add_argument("--mode", choices=["demo", "llm"], default="demo")
    parser.add_argument("--suite", choices=["full", "smoke"], default="full")
    parser.add_argument("--delay-seconds", type=float, default=0, help="Pause between requests to respect quotas.")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    settings = Settings()
    if args.mode == "llm" and not settings.llm_enabled:
        parser.error("LLM benchmark requires an OpenAI or Groq key configured on the server.")
    if args.mode == "demo" and args.suite != "full":
        parser.error("The smoke suite is specific to LLM mode.")
    if not isfinite(args.delay_seconds) or args.delay_seconds < 0:
        parser.error("--delay-seconds must be finite and nonnegative.")
    if not settings.database_path.is_file():
        parser.error("Build the database first with python -m scripts.build_database.")
    llm = args.mode == "llm"
    planner = build_llm_planner(settings) if llm else DeterministicPlanner()
    report = run_benchmark(
        AnalyticsAgent(AnalyticsTools(settings.database_path), planner, args.mode),
        suite=args.suite, delay_seconds=args.delay_seconds,
        provider=settings.llm_provider if llm else None, model=settings.llm_model if llm else None,
    )
    output = args.output or (settings.llm_report_path if llm else REPORT)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    for name in ("overall", "numeric_accuracy", "sql_success", "groundedness", "unsafe_rejection"):
        score = getattr(report, name)
        print(f"{name}: {score.passed}/{score.total}")
    for name, score in report.categories.items():
        print(f"  {name}: {score.passed}/{score.total}")
    for case in report.cases:
        if not case.passed:
            print(f"FAIL {case.id} {case.question} {' '.join(case.failure_reasons)}")
    print(f"Latency (ms): {report.latency_ms}")
    print(f"Report: {output}")
    return int(report.overall.passed != report.overall.total)


if __name__ == "__main__":
    raise SystemExit(main())
