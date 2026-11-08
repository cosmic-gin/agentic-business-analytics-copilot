from math import isclose

from backend.app.agent.answer import generate_answer
from backend.app.agent.planning import Planner, guard_question, validate_plan
from backend.app.agent.state import State
from backend.app.schemas.agent import Quality
from backend.app.services.analytics import AnalyticsTools, category_drivers


class EvidenceError(RuntimeError):
    pass


def build_nodes(planner: Planner, tools: AnalyticsTools):
    def interpret(state: State) -> State:
        guard_question(state["question"])
        plan, usage = planner.interpret(state["question"])
        return {"plan": plan, "usage": usage}

    def validate(state: State) -> State:
        return {"plan": validate_plan(state["plan"])}

    def definition(state: State) -> State:
        return {"definition": tools.get_kpi_definition(state["plan"].metric)}

    def plan(state: State) -> State:
        proposal = state["plan"]
        match proposal.intent:
            case "quality":
                query_ids = []
            case "breakdown":
                query_ids = [f"{proposal.dimension}_breakdown"]
            case "drivers":
                query_ids = ["monthly_kpi", "category_breakdown"]
            case _:
                query_ids = ["monthly_kpi"]
        return {"query_ids": query_ids}

    def select(state: State) -> State:
        allowed = {"monthly_kpi", "category_breakdown", "warehouse_breakdown", "carrier_breakdown"}
        if len(state["query_ids"]) > 2 or set(state["query_ids"]) - allowed:
            raise EvidenceError("Invalid tool recipe")
        return {}

    def execute(state: State) -> State:
        proposal = state["plan"]
        scope = proposal.scope
        if not state["query_ids"]:
            return {"evidence": []}
        if proposal.intent == "breakdown":
            return {"evidence": [tools.get_breakdown(proposal.dimension, scope)]}
        if proposal.intent not in {"compare", "drivers"}:
            return {"evidence": [tools.get_monthly_kpi(scope)]}

        comparison, evidence = tools.compare_kpi_periods(scope, proposal.metric)
        result: State = {"comparison": comparison, "evidence": [evidence]}
        if proposal.intent == "drivers":
            breakdown = tools.get_category_breakdown(scope)
            result["evidence"].append(breakdown)
            endpoints = [row for row in breakdown.rows if row["period"] in {scope.start, scope.end}]
            result["drivers"] = category_drivers(comparison, breakdown.model_copy(update={"rows": endpoints}))
        return result

    def quality(state: State) -> State:
        evidence = tools.check_data_quality(state["plan"].scope)
        row = evidence.rows[0]
        records, valid = row["records"], row["valid_deliveries"]
        return {"evidence": [*state["evidence"], evidence], "quality": Quality(
            **row, excluded=records - valid, completeness_pct=100 * valid / records if records else None,
        )}

    def verify(state: State) -> State:
        evidence, quality = state["evidence"], state["quality"]
        if quality.excluded < 0:
            raise EvidenceError("Invalid data quality counts")
        for query in evidence[:-1]:
            total_valid = 0
            for row in query.rows:
                valid, on_time, late = (row[key] for key in
                                        ("valid_deliveries", "on_time_deliveries", "late_deliveries"))
                if valid <= 0 or min(on_time, late) < 0 or valid != on_time + late or not (
                    isclose(row["on_time_rate"], 100 * on_time / valid)
                    and isclose(row["late_rate"], 100 * late / valid)
                ):
                    raise EvidenceError("KPI evidence did not reconcile")
                total_valid += valid
            if total_valid != quality.valid_deliveries:
                raise EvidenceError("Quality and query cohorts did not reconcile")
        if state["plan"].intent == "drivers":
            drivers, comparison = state["drivers"], state["comparison"]
            for prefix in ("previous", "current"):
                for count in ("late", "valid"):
                    key = f"{prefix}_{count}"
                    if sum(getattr(row, key) for row in drivers) != getattr(comparison, key):
                        raise EvidenceError("Category totals did not reconcile")
        return {}

    return {
        "interpret": interpret, "validate": validate, "definition": definition,
        "plan": plan, "select": select, "execute": execute, "quality": quality,
        "verify": verify, "answer": generate_answer,
    }
