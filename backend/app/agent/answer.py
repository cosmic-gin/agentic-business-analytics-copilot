from backend.app.agent.state import State
from backend.app.schemas.agent import Chart, Finding
from backend.app.services.analytics import FILTER_CATALOG, RATES


def generate_answer(state: State) -> State:
    plan, quality = state["plan"], state["quality"]
    label = state["definition"]["label"]
    scope_label = plan.scope.start
    if plan.scope.end != plan.scope.start:
        scope_label += f" through {plan.scope.end}"
    caveats = ["Simulated snapshot. Reporting periods use the UTC promised-delivery month."]
    filters = plan.scope.model_dump()
    labels = [members[filters[field]] for field, members in FILTER_CATALOG.items()
              if filters[field] is not None]
    if labels:
        caveats.append(f"Filters applied: {', '.join(labels)}.")
    if quality.excluded:
        caveats.append(f"{quality.excluded:,} of {quality.records:,} scoped records were excluded "
                       "from KPI calculations. See data quality for the reasons.")
    if plan.intent == "quality":
        return {
            "summary": f"{quality.valid_deliveries:,} of {quality.records:,} records qualified for delivery KPIs "
                       f"in {scope_label}. {quality.excluded:,} records were excluded.",
            "supporting": state["evidence"][-1].rows, "caveats": caveats,
        }

    unit = "percent" if plan.metric in RATES else "count"

    def fmt(value):
        if value is None:
            return "unavailable"
        return f"{value:.2f}%" if unit == "percent" else f"{value:,.0f}"

    primary = state["evidence"][0]
    rows = primary.rows
    chart = None
    findings = []
    comparison = state.get("comparison")
    drivers = state.get("drivers", [])
    if comparison:
        summary = f"{label} moved from {fmt(comparison.previous_value)} in {comparison.previous_period} "
        summary += f"to {fmt(comparison.current_value)} in {comparison.current_period}"
        if comparison.change_pp is not None:
            summary += f", a {comparison.change_pp:+.2f} percentage-point change"
        summary += "."
        rows = [row for row in rows if row["period"] in {plan.scope.start, plan.scope.end}]
        if drivers:
            top = drivers[0]
            tied = [driver.category for driver in drivers if driver.late_count_change == top.late_count_change]
            if top.late_count_change > 0:
                phrasing = "had the largest increase" if len(tied) == 1 else "tied for the largest increase"
                summary += f" {', '.join(tied)} {phrasing} in late-delivery count (+{top.late_count_change})."
            else:
                summary += " No category increased its late-delivery count."
            if top.late_rate_contribution_pp is not None:
                detail = (f"{top.previous_late} of {top.previous_valid} valid category deliveries were late in "
                          f"{comparison.previous_period}, versus {top.current_late} of {top.current_valid} in "
                          f"{comparison.current_period}. This category contributed "
                          f"{top.late_rate_contribution_pp:+.2f} points to the overall late-rate change.")
                if top.within_category_effect_pp is not None:
                    detail += (f" Within-category rate effect {top.within_category_effect_pp:+.3f} points. "
                               f"Category mix effect {top.category_mix_effect_pp:+.3f} points.")
                findings.append(Finding(title=top.category, detail=detail,
                                        evidence_ids=[primary.query_id, state["evidence"][1].query_id]))
            caveats.append("Category contributions describe the observed change. Shipment records lack operational cause data.")
            chart = Chart(kind="bar", title="Late deliveries by category", x_key="category",
                          series={"before": comparison.previous_period, "after": comparison.current_period},
                          unit="count", rows=[{"category": driver.category, "before": driver.previous_late,
                                               "after": driver.current_late} for driver in drivers])
    elif not rows:
        summary = f"No valid completed deliveries were found in {scope_label}."
    elif plan.intent == "breakdown":
        rank = max if plan.ranking == "highest" else min
        extreme = rank(row[plan.metric] for row in rows)
        names = ", ".join(str(row["name"]) for row in rows if row[plan.metric] == extreme)
        summary = f"{names} recorded the {plan.ranking} {label.lower()} in {scope_label} at {fmt(extreme)}."
        chart = Chart(kind="bar", title=f"{label} by {plan.dimension}", x_key="name",
                      series={plan.metric: label}, unit=unit, rows=rows)
    elif plan.intent == "trend":
        summary = (f"{label} was {fmt(rows[0][plan.metric])} in {rows[0]['period']} "
                   f"and {fmt(rows[-1][plan.metric])} in {rows[-1]['period']}.")
    else:
        row = rows[0]
        summary = f"{label} in {row['period']} was {fmt(row[plan.metric])} across {row['valid_deliveries']:,} valid deliveries."

    if chart is None and rows:
        chart = Chart(kind="line" if len(rows) > 1 else "bar", title=label, x_key="period",
                      series={plan.metric: label}, unit=unit, rows=rows)
    return {"summary": summary, "supporting": rows, "chart": chart, "findings": findings, "caveats": caveats}
