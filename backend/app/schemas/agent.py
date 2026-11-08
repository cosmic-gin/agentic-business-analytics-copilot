from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.app.core.config import ProviderName
from backend.app.schemas.analytics import (
    Dimension,
    Driver,
    KPIComparison,
    Metric,
    QueryEvidence,
    Row,
    Scope,
)

Mode = Literal["demo", "llm"]
Status = Literal["ok", "ambiguous", "unsupported", "rejected", "error"]
Intent = Literal["monthly", "compare", "trend", "breakdown", "drivers", "quality"]
Ranking = Literal["highest", "lowest"]


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    question: str = Field(min_length=3, max_length=600)
    mode: Mode | None = None


class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    intent: Intent
    metric: Metric
    scope: Scope
    dimension: Dimension | None = None
    ranking: Ranking = "highest"


class WorkflowStep(BaseModel):
    key: str
    label: str
    status: Literal["pending", "running", "successful", "failed", "skipped"]
    elapsed_ms: float | None = None


class Finding(BaseModel):
    title: str
    detail: str
    evidence_ids: list[str]


class Chart(BaseModel):
    kind: Literal["line", "bar"]
    title: str
    x_key: str
    series: dict[str, str]
    unit: Literal["percent", "count"]
    rows: list[Row]


class Quality(BaseModel):
    records: int
    valid_deliveries: int
    excluded: int
    completeness_pct: float | None
    pending: int
    cancelled: int
    missing_actual: int
    missing_promise: int
    after_cutoff: int


class Usage(BaseModel):
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float | None = None
    provider: ProviderName | None = None
    model: str | None = None


class Execution(BaseModel):
    elapsed_ms: float
    query_count: int
    dataset_version: str
    request_id: str | None = None
    provider_usage: Usage | None = None


class AnalysisResponse(BaseModel):
    question: str
    mode: Mode
    status: Status
    summary: str
    plan: Plan | None = None
    kpi_definition: dict[str, str] | None = None
    kpi_comparison: KPIComparison | None = None
    findings: list[Finding] = Field(default_factory=list)
    drivers: list[Driver] = Field(default_factory=list)
    supporting_evidence: list[Row] = Field(default_factory=list)
    chart_data: Chart | None = None
    sql_evidence: list[QueryEvidence] = Field(default_factory=list)
    data_quality: Quality | None = None
    caveats: list[str] = Field(default_factory=list)
    workflow_steps: list[WorkflowStep]
    execution_metadata: Execution


class StepEvent(BaseModel):
    type: Literal["step"] = "step"
    step: WorkflowStep


class ResultEvent(BaseModel):
    type: Literal["result"] = "result"
    result: AnalysisResponse
