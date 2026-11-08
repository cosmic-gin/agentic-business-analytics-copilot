import logging
from time import perf_counter

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import ValidationError

from backend.app.agent.graph import AnalyticsAgent
from backend.app.agent.planning import DeterministicPlanner
from backend.app.agent.providers import build_llm_planner
from backend.app.core.config import ROOT, Settings
from backend.app.db.reader import QueryFailed
from backend.app.schemas.agent import AnalysisResponse, AskRequest, Mode
from backend.app.schemas.api import (
    ErrorResponse,
    EvaluationReport,
    EvaluationResponse,
    Example,
    Health,
    KPIs,
    Metadata,
)
from backend.app.services.analytics import DATASET, KPI_DEFINITIONS, AnalyticsTools

logger = logging.getLogger(__name__)
EXAMPLES = [
    Example(label="May delivery decline", question="Why did our on-time delivery performance decrease in May 2026, and which product category contributed most?"),
    Example(label="Monthly trend", question="Show the monthly on-time delivery trend."),
    Example(label="Warehouse comparison", question="Which warehouse has the highest late-delivery rate?"),
    Example(label="Carrier comparison", question="Which carrier performs worst?"),
    Example(label="Category breakdown", question="Which product category had the most late deliveries in May?"),
    Example(label="Data quality", question="Are missing or incomplete records affecting the KPI in October?"),
]
REPORT_PATH = ROOT / "evals/reports/demo-v1.json"
NDJSON = "application/x-ndjson"
LLM_EXAMPLE = Example(label="Safety & Control in May",
                      question="What share of Safety & Control shipments met their delivery promise in May 2026?")


def build_router(settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/api", responses={
        422: {"model": ErrorResponse}, 503: {"model": ErrorResponse},
    })
    tools = AnalyticsTools(settings.database_path)
    agents: dict[Mode, AnalyticsAgent] = {"demo": AnalyticsAgent(tools, DeterministicPlanner())}
    if settings.app_mode == "llm" and not settings.llm_enabled:
        raise ValueError("APP_MODE=llm requires LLM_PROVIDER and its server-side API key.")
    if settings.llm_enabled:
        agents["llm"] = AnalyticsAgent(tools, build_llm_planner(settings), "llm")
    default_mode = settings.app_mode

    @router.get("/health", response_model=Health, responses={503: {"model": Health}})
    def health():
        try:
            tools.reader.run("health", {})
        except QueryFailed:
            return JSONResponse(status_code=503, content=Health(status="degraded").model_dump())
        return Health()

    @router.get("/metadata")
    def metadata() -> Metadata:
        try:
            overview = tools.overview()
        except QueryFailed as error:
            raise HTTPException(503, "The analytics dataset is unavailable.") from error
        return Metadata(dataset=DATASET, overview=overview.rows[0] if overview.rows else {},
                        enabled_modes=list(agents), default_mode=default_mode,
                        llm_provider=settings.llm_provider if settings.llm_enabled else None,
                        llm_model=settings.llm_model if settings.llm_enabled else None)

    @router.get("/kpis")
    def kpis() -> KPIs:
        return KPIs(**KPI_DEFINITIONS)

    @router.get("/examples")
    def examples(mode: Mode = "demo") -> list[Example]:
        return [*EXAMPLES, LLM_EXAMPLE] if mode == "llm" and "llm" in agents else EXAMPLES

    @router.get("/evaluations")
    def evaluations(mode: Mode = "demo") -> EvaluationResponse:
        if mode not in agents:
            return EvaluationResponse(status="unavailable")
        path = settings.llm_report_path if mode == "llm" else REPORT_PATH
        try:
            report = EvaluationReport.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValidationError):
            return EvaluationResponse(status="unavailable")
        if report.mode != mode or report.dataset_version != DATASET["version"] or (
            mode == "llm" and (report.provider, report.model) != (settings.llm_provider, settings.llm_model)
        ):
            return EvaluationResponse(status="unavailable")
        return EvaluationResponse(status="available", report=report)

    def resolve_agent(payload: AskRequest) -> AnalyticsAgent:
        if payload.mode and payload.mode not in agents:
            raise HTTPException(503, "LLM mode is unavailable. Choose demo mode or configure the server.")
        return agents[payload.mode or default_mode]

    @router.post("/ask")
    def ask(payload: AskRequest, request: Request) -> AnalysisResponse:
        agent = resolve_agent(payload)
        return agent.ask(payload.question, request.state.request_id)

    @router.post("/ask/stream", responses={200: {"content": {NDJSON: {
        "schema": {"type": "string", "description": "Newline-delimited step events followed by a result or error."},
    }}}})
    def ask_stream(payload: AskRequest, request: Request):
        agent = resolve_agent(payload)
        request_id = request.state.request_id

        def lines():
            started = perf_counter()
            try:
                for event in agent.stream(payload.question, request_id):
                    yield event.model_dump_json() + "\n"
            except Exception as error:
                logger.error("stream_failed request_id=%s error_type=%s", request_id, type(error).__name__)
                yield '{"type":"error","message":"Analysis stream failed. Try again."}\n'
            finally:
                logger.info("stream_finished request_id=%s elapsed_ms=%.2f",
                            request_id, (perf_counter() - started) * 1000)

        return StreamingResponse(lines(), media_type=NDJSON, headers={
            "Cache-Control": "no-store", "X-Accel-Buffering": "no",
        })

    return router
