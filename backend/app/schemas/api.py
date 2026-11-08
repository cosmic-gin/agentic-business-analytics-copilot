from typing import Literal

from pydantic import BaseModel

from backend.app.core.config import ProviderName
from backend.app.schemas.agent import Mode
from backend.app.schemas.analytics import Row


class Health(BaseModel):
    status: Literal["ok", "degraded"] = "ok"
    api_version: Literal["v1"] = "v1"


class Dataset(BaseModel):
    version: str
    simulated: bool
    seed: int
    first_month: str
    latest_month: str
    cutoff_exclusive: str
    currency: str


class Metadata(BaseModel):
    dataset: Dataset
    overview: Row
    enabled_modes: list[Mode]
    default_mode: Mode
    llm_provider: ProviderName | None = None
    llm_model: str | None = None


class KPIs(BaseModel):
    reporting_month: str
    valid_delivery: str
    exclusions: str
    metrics: dict[str, dict[str, str]]


class Example(BaseModel):
    label: str
    question: str


class EvaluationCase(BaseModel):
    id: str
    category: str
    question: str
    expected_status: str
    actual_status: str
    passed: bool
    numeric_match: bool | None
    sql_success: bool | None
    grounded: bool | None
    unsafe_rejected: bool | None
    elapsed_ms: float
    estimated_cost_usd: float | None = None
    failure_reasons: list[str]


class EvaluationMetric(BaseModel):
    passed: int
    total: int
    rate: float | None


class EvaluationReport(BaseModel):
    benchmark_version: str
    dataset_version: str
    mode: Mode
    provider: ProviderName | None = None
    model: str | None = None
    generated_at: str
    overall: EvaluationMetric
    numeric_accuracy: EvaluationMetric
    sql_success: EvaluationMetric
    groundedness: EvaluationMetric
    unsafe_rejection: EvaluationMetric
    latency_ms: dict[str, float]
    average_cost_usd: float | None = None
    cost_status: Literal["not_applicable", "unavailable", "measured"]
    categories: dict[str, EvaluationMetric]
    cases: list[EvaluationCase]


class EvaluationResponse(BaseModel):
    status: Literal["available", "unavailable"]
    report: EvaluationReport | None = None


class APIError(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: APIError
    request_id: str
