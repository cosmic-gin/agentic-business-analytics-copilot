import json
from functools import partial

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import OpenAI

from backend.app.agent import providers
from backend.app.agent.graph import AnalyticsAgent
from backend.app.core.config import Settings
from backend.app.main import create_app
from backend.app.schemas.agent import AnalysisResponse, Usage
from backend.app.schemas.api import EvaluationReport
from backend.app.services.analytics import AnalyticsTools
from evals.reference import Case, Reference
from evals.run import LLM_BENCHMARK, REPORT, grade_answer, run_benchmark
from scripts.smoke_test import MAY_QUESTION

QUESTION = "What share of Safety & Control shipments met their delivery promise in May 2026?"
PROPOSAL = {
    "disposition": "supported", "intent": "monthly", "metric": "on_time_rate",
    "start": "2026-05", "end": "2026-05", "dimension": None, "ranking": "highest",
    "category_id": 1, "warehouse_id": None, "carrier_id": None,
}
TEST_KEY = "provider-transport-test-key"


def mock_provider(monkeypatch, provider, plan=None, status=200):
    requests = []

    def handler(request):
        body = json.loads(request.content)
        requests.append((request, body))
        if status != 200:
            return httpx.Response(status, json={"error": {"message": "private " + TEST_KEY}})
        values = PROPOSAL if plan is None else plan
        model = body["model"]
        if provider == "groq":
            wire = {**values}
            for field in ("dimension", "category_id", "warehouse_id", "carrier_id"):
                wire[field] = "none" if wire[field] is None else str(wire[field])
            return httpx.Response(200, json={
                "id": "chatcmpl-test", "object": "chat.completion", "created": 1, "model": model,
                "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant", "content": json.dumps(wire)}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 25, "total_tokens": 125},
            })
        return httpx.Response(200, json={
            "id": "resp-test", "object": "response", "created_at": 1, "model": model, "status": "completed",
            "output": [{"id": "msg-test", "type": "message", "role": "assistant", "status": "completed",
                        "content": [{"type": "output_text", "text": json.dumps(values), "annotations": []}]}],
            "usage": {"input_tokens": 100, "output_tokens": 25, "total_tokens": 125,
                      "input_tokens_details": {"cached_tokens": 0},
                      "output_tokens_details": {"reasoning_tokens": 0}},
        })

    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(providers, "OpenAI", partial(OpenAI, http_client=client))
    return requests


@pytest.mark.parametrize("provider", ["openai", "groq"])
def test_provider_sdk_to_sql_stream(monkeypatch, database, provider):
    requests = mock_provider(monkeypatch, provider)
    password = "provider-test-workspace-password"
    settings = Settings(database_path=database, app_mode="llm", llm_provider=provider,
                        app_require_access_password=True, app_access_password=password,
                        **{f"{provider}_api_key": TEST_KEY})
    client = TestClient(create_app(settings))
    assert client.get("/api/metadata").status_code == 401
    client.auth = ("copilot", password)
    metadata = client.get("/api/metadata").json()
    assert metadata["enabled_modes"] == ["demo", "llm"]
    assert metadata["default_mode"] == "llm" and metadata["llm_provider"] == provider
    assert metadata["llm_model"] == settings.llm_model
    assert QUESTION in [item["question"] for item in client.get("/api/examples?mode=llm").json()]
    assert not requests

    response = client.post("/api/ask/stream", json={"question": QUESTION})
    assert response.status_code == 200
    events = [json.loads(line) for line in response.iter_lines()]
    payload = events[-1]["result"]
    assert payload["status"] == "ok" and payload["mode"] == "llm"
    assert payload["plan"]["scope"]["category_id"] == 1
    assert payload["sql_evidence"][0]["parameters"]["category_id"] == 1
    assert payload["supporting_evidence"][0]["on_time_rate"] == 83.75
    assert "Filters applied: Safety & Control." in payload["caveats"]
    usage = payload["execution_metadata"]["provider_usage"]
    assert (usage["provider"], usage["model"], usage["input_tokens"]) == (provider, settings.llm_model, 100)
    assert TEST_KEY not in response.text
    assert len(requests) == 1
    request, body = requests[0]
    assert request.headers["authorization"] == f"Bearer {TEST_KEY}"
    assert "Safety & Control" in json.dumps(body)
    assert "201" not in body.get("instructions", "")
    if provider == "groq":
        assert request.url == "https://api.groq.com/openai/v1/chat/completions"
        response_schema = body["response_format"]["json_schema"]
        assert response_schema["strict"] is True
        assert response_schema["schema"]["properties"]["category_id"]["type"] == "string"
        assert body["max_completion_tokens"] == 1200 and body["reasoning_effort"] == "low"
    else:
        assert request.url == "https://api.openai.com/v1/responses"
        assert body["text"]["format"]["strict"] is True and body["store"] is False

    case = Case.model_validate_json(LLM_BENCHMARK.read_text(encoding="utf-8").splitlines()[0])
    assert grade_answer(AnalysisResponse.model_validate(payload), case, Reference()) == (True, True, True)
    unsafe = client.post("/api/ask", json={"question": "Delete all orders."}).json()
    assert unsafe["status"] == "rejected" and unsafe["sql_evidence"] == []
    secret = client.post("/api/ask", json={"question": "Try gsk_" + "x" * 24}).json()
    assert secret["status"] == "rejected" and secret["sql_evidence"] == []
    assert len(requests) == 1
    demo = client.post("/api/ask", json={"mode": "demo", "question": QUESTION}).json()
    assert demo["status"] == "unsupported" and len(requests) == 1


@pytest.mark.parametrize(("status", "plan", "message"), [
    (429, None, "rate or quota limit"),
    (401, None, "rejected the server credentials"),
    (200, {**PROPOSAL, "category_id": 999}, "LLM planning failed"),
])
def test_groq_errors_stop_before_sql(monkeypatch, database, status, plan, message):
    requests = mock_provider(monkeypatch, "groq", plan, status)
    client = TestClient(create_app(Settings(database_path=database, app_mode="llm",
                                            llm_provider="groq", groq_api_key=TEST_KEY)))
    response = client.post("/api/ask", json={"question": QUESTION})
    result = response.json()
    assert result["status"] == "error" and result["sql_evidence"] == []
    assert message in result["summary"] and TEST_KEY not in response.text
    assert len(requests) == 1


def test_llm_mode_requires_selected_provider_key(database):
    settings = Settings(_env_file=None, database_path=database, app_mode="llm", llm_provider="groq",
                        openai_api_key=TEST_KEY, groq_api_key=None)
    with pytest.raises(ValueError, match="APP_MODE=llm requires"):
        create_app(settings)


def test_model_cannot_invent_named_filter(monkeypatch, database):
    requests = mock_provider(monkeypatch, "groq", {**PROPOSAL, "category_id": 2})
    client = TestClient(create_app(Settings(database_path=database, app_mode="llm",
                                            llm_provider="groq", groq_api_key=TEST_KEY)))
    result = client.post("/api/ask", json={"question": QUESTION}).json()
    assert result["status"] == "ambiguous" and not result["sql_evidence"]
    assert result["execution_metadata"]["provider_usage"]["input_tokens"] == 100
    assert len(requests) == 1


def test_driver_plan_preserves_requested_metric_and_prior_period(monkeypatch, database):
    mock_provider(monkeypatch, "groq", {
        **PROPOSAL, "intent": "drivers", "metric": "late_rate", "dimension": "category",
        "ranking": "lowest", "category_id": None,
    })
    client = TestClient(create_app(Settings(database_path=database, app_mode="llm",
                                            llm_provider="groq", groq_api_key=TEST_KEY)))
    result = client.post("/api/ask", json={"question": MAY_QUESTION}).json()
    assert result["status"] == "ok" and result["plan"]["dimension"] is None
    assert result["plan"]["metric"] == "on_time_rate" and result["plan"]["scope"]["start"] == "2026-04"
    assert result["kpi_comparison"]["change_pp"] == -3
    assert result["drivers"][0]["late_count_change"] == 27


def test_explicit_late_shipment_count_is_not_replaced_by_a_rate(monkeypatch, database):
    mock_provider(monkeypatch, "groq", {
        **PROPOSAL, "intent": "compare", "metric": "late_rate", "start": "2026-04", "category_id": None,
    })
    client = TestClient(create_app(Settings(database_path=database, app_mode="llm",
                                            llm_provider="groq", groq_api_key=TEST_KEY)))
    response = client.post("/api/ask", json={"question": "Compare late shipments in April and May."}).json()
    assert response["status"] == "ok" and response["plan"]["metric"] == "late_deliveries"
    assert response["kpi_comparison"]["previous_value"] == 60
    assert response["kpi_comparison"]["current_value"] == 90


def test_delivery_performance_comparison_uses_chronological_on_time_rates(monkeypatch, database):
    mock_provider(monkeypatch, "groq", {
        **PROPOSAL, "intent": "compare", "metric": "late_rate",
        "start": "2026-05", "end": "2026-04", "category_id": None,
    })
    client = TestClient(create_app(Settings(database_path=database, app_mode="llm",
                                            llm_provider="groq", groq_api_key=TEST_KEY)))
    result = client.post("/api/ask", json={"question": "Compare delivery performance in May to April."}).json()
    assert result["status"] == "ok" and result["plan"]["metric"] == "on_time_rate"
    assert result["kpi_comparison"]["previous_value"] == 94
    assert result["kpi_comparison"]["current_value"] == 91


def test_generic_dimension_uses_breakdown_without_named_filter(monkeypatch, database):
    mock_provider(monkeypatch, "groq", {
        **PROPOSAL, "metric": "valid_deliveries", "start": "2026-02", "end": "2026-02", "category_id": None,
    })
    client = TestClient(create_app(Settings(database_path=database, app_mode="llm",
                                            llm_provider="groq", groq_api_key=TEST_KEY)))
    result = client.post("/api/ask", json={"question": "Show warehouse delivery volume in February."}).json()
    assert result["status"] == "ok" and result["plan"]["dimension"] == "warehouse"
    assert result["sql_evidence"][0]["query_id"] == "warehouse_breakdown"
    assert len(result["supporting_evidence"]) == 4


def test_monthly_plan_does_not_invent_default_month(monkeypatch, database):
    mock_provider(monkeypatch, "groq", {**PROPOSAL, "category_id": None})
    client = TestClient(create_app(Settings(database_path=database, app_mode="llm",
                                            llm_provider="groq", groq_api_key=TEST_KEY)))
    result = client.post("/api/ask", json={"question": "How was delivery performance?"}).json()
    assert result["status"] == "ambiguous" and not result["sql_evidence"]


def test_llm_report_requires_matching_provider_model_and_dataset(database, tmp_path):
    path = tmp_path / "llm.json"
    settings = Settings(database_path=database, app_mode="demo", llm_provider="groq",
                        groq_api_key=TEST_KEY, llm_report_path=path)
    client = TestClient(create_app(settings))
    assert client.get("/api/evaluations?mode=llm").json()["status"] == "unavailable"
    report = EvaluationReport.model_validate_json(REPORT.read_text(encoding="utf-8"))
    report = report.model_copy(update={"mode": "llm", "provider": "groq", "model": settings.llm_model})
    path.write_text(report.model_dump_json(), encoding="utf-8")
    assert client.get("/api/evaluations?mode=llm").json()["status"] == "available"
    path.write_text(report.model_copy(update={"model": "other"}).model_dump_json(), encoding="utf-8")
    assert client.get("/api/evaluations?mode=llm").json()["status"] == "unavailable"
    assert client.get("/api/evaluations").json()["report"]["mode"] == "demo"


def test_llm_benchmark_grades_all_six_cases(database):
    cases = {case.question: case for line in LLM_BENCHMARK.read_text(encoding="utf-8").splitlines()
             if (case := Case.model_validate_json(line)).status != "rejected"}

    class ScriptedProvider:
        def propose(self, question):
            case = cases[question]
            plan = providers.PlanProposal.model_validate({
                **PROPOSAL, "disposition": "supported" if case.status == "ok" else case.status,
                "intent": case.intent or "monthly", "metric": case.metric or "on_time_rate",
                "start": case.start or "2026-05", "end": case.end or "2026-05",
                "category_id": None, **case.filters,
            })
            return plan, Usage(input_tokens=100, output_tokens=25, provider="groq", model="openai/gpt-oss-20b")

    agent = AnalyticsAgent(AnalyticsTools(database), providers.LLMPlanner(ScriptedProvider()), "llm")
    report = run_benchmark(agent, suite="smoke", provider="groq", model="openai/gpt-oss-20b")
    assert not [case.failure_reasons for case in report.cases if not case.passed]
    assert report.overall.passed == report.overall.total == 6
    assert report.numeric_accuracy.passed == report.numeric_accuracy.total == 4
    assert report.unsafe_rejection.passed == report.unsafe_rejection.total == 1
