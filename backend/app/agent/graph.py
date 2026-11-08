import logging
from collections.abc import Iterator
from time import perf_counter

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph

from backend.app.agent.nodes import EvidenceError, build_nodes
from backend.app.agent.planning import Planner, PlanningIssue
from backend.app.agent.state import STEPS, State
from backend.app.db.reader import QueryFailed
from backend.app.schemas.agent import (
    AnalysisResponse,
    Execution,
    Mode,
    ResultEvent,
    StepEvent,
    WorkflowStep,
)
from backend.app.services.analytics import DATASET, AnalyticsTools

logger = logging.getLogger(__name__)


def tracked(key, node):
    def run(state: State) -> State:
        started = perf_counter()
        emit = get_stream_writer()
        if key == "execute" and not state["query_ids"]:
            step = WorkflowStep(key=key, label=STEPS[key], status="skipped")
            emit(StepEvent(step=step))
            return {**node(state), "steps": [*state["steps"], step]}
        emit(StepEvent(step=WorkflowStep(key=key, label=STEPS[key], status="running")))
        try:
            update = node(state)
            status = "successful"
        except PlanningIssue as issue:
            status = "failed"
            update = {"status": issue.status, "summary": str(issue)}
            if issue.usage is not None:
                update["usage"] = issue.usage
        except (QueryFailed, EvidenceError, ValueError, TypeError, KeyError) as error:
            logger.warning("workflow_failed node=%s error_type=%s", key, type(error).__name__)
            status = "failed"
            update = {"status": "error", "summary": "The analysis could not be verified. Check the dataset and try again."}
        step = WorkflowStep(key=key, label=STEPS[key], status=status,
                            elapsed_ms=round((perf_counter() - started) * 1000, 2))
        emit(StepEvent(step=step))
        return {**update, "steps": [*state["steps"], step]}
    return run


def route(state: State):
    return "continue" if state["status"] == "ok" else "stop"


class AnalyticsAgent:
    def __init__(self, tools: AnalyticsTools, planner: Planner, mode: Mode = "demo"):
        graph = StateGraph(State)
        for key, node in build_nodes(planner, tools).items():
            graph.add_node(key, tracked(key, node))
        keys = list(STEPS)
        graph.add_edge(START, keys[0])
        for current, following in zip(keys, keys[1:]):
            graph.add_conditional_edges(current, route, {"continue": following, "stop": END})
        graph.add_edge(keys[-1], END)
        self.graph = graph.compile()
        self.mode = mode

    def stream(self, question: str, request_id: str | None = None) -> Iterator[StepEvent | ResultEvent]:
        started = perf_counter()
        final = {}
        for channel, event in self.graph.stream(
            {"question": question, "status": "ok", "steps": []},
            config={"recursion_limit": 12}, stream_mode=["custom", "values"], version="v1",
        ):
            if channel == "custom":
                yield event
            else:
                final = event
        steps = final["steps"]
        for key in list(STEPS)[len(steps):]:
            step = WorkflowStep(key=key, label=STEPS[key], status="skipped")
            steps.append(step)
            yield StepEvent(step=step)
        evidence = final.get("evidence", [])
        verified = final["status"] == "ok"
        yield ResultEvent(result=AnalysisResponse(
            question=question, mode=self.mode, status=final["status"], summary=final["summary"],
            plan=final.get("plan"), kpi_definition=final.get("definition"),
            kpi_comparison=final.get("comparison") if verified else None,
            findings=final.get("findings", []), drivers=final.get("drivers", []) if verified else [],
            supporting_evidence=final.get("supporting", []), chart_data=final.get("chart"),
            sql_evidence=evidence, data_quality=final.get("quality"), caveats=final.get("caveats", []),
            workflow_steps=steps, execution_metadata=Execution(
                elapsed_ms=round((perf_counter() - started) * 1000, 2), query_count=len(evidence),
                dataset_version=DATASET["version"], request_id=request_id, provider_usage=final.get("usage"),
            ),
        ))

    def ask(self, question: str, request_id: str | None = None) -> AnalysisResponse:
        for event in self.stream(question, request_id):
            if isinstance(event, ResultEvent):
                return event.result
        raise RuntimeError("Workflow returned no result")
