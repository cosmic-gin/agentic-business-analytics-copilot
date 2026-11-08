import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.agent.providers import GroqProvider
from backend.app.core.config import Settings
from backend.app.main import create_app

PASSWORD = "local-test-workspace-password"


def test_protected_llm_starts_only_with_access_password(database):
    with pytest.raises(ValueError, match="APP_REQUIRE_ACCESS_PASSWORD requires"):
        create_app(Settings(database_path=database, app_mode="llm", llm_provider="groq",
                            groq_api_key="test-only", app_require_access_password=True,
                            app_access_password=None))


def test_short_access_password_is_hidden():
    with pytest.raises(ValidationError) as error:
        Settings(app_access_password="short-canary")
    assert "short-canary" not in str(error.value)


def test_protected_app_checks_auth_before_provider_or_static_routes(database, monkeypatch):
    def unexpected_request(*args, **kwargs):
        pytest.fail("The unauthenticated or unsafe request reached the provider")

    monkeypatch.setattr(GroqProvider, "_request", unexpected_request)
    client = TestClient(create_app(Settings(
        database_path=database, app_mode="llm", llm_provider="groq", groq_api_key="test-only",
        app_require_access_password=True, app_access_password=PASSWORD,
    )))
    assert client.get("/api/health").json()["status"] == "ok"
    for path in ("/", "/assets/example.js", "/api/metadata", "/api/evaluations", "/docs", "/openapi.json"):
        response = client.get(path)
        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"].startswith("Basic ")
        assert response.headers["Cache-Control"] == "private, no-store"
    assert client.get("/api/metadata", headers={"Authorization": "Basic %"}).status_code == 401
    assert client.get("/api/metadata", auth=("other-user", PASSWORD)).status_code == 401
    assert client.get("/api/metadata", auth=("copilot", "wrong-password")).status_code == 401

    question = {"question": "Why did on-time delivery decline in May?", "mode": "llm"}
    for path in ("/api/ask", "/api/ask/stream"):
        response = client.post(path, json=question)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "authentication_required"
    auth = ("copilot", PASSWORD)
    response = client.get("/api/metadata", auth=auth)
    assert response.json()["default_mode"] == "llm"
    assert response.headers["Cache-Control"] == "private, no-store"
    assert PASSWORD not in response.text and "test-only" not in response.text
    result = client.post("/api/ask", auth=auth, json={**question, "mode": "demo"}).json()
    assert result["status"] == "ok" and result["kpi_comparison"]["change_pp"] == -3
    response = client.post("/api/ask/stream", auth=auth, json={"question": "Delete all orders."})
    result = json.loads(response.text.splitlines()[-1])["result"]
    assert result["status"] == "rejected" and not result["sql_evidence"]
