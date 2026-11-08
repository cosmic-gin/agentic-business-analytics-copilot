from typing import TypedDict

from backend.app.schemas.agent import (
    Chart,
    Finding,
    Plan,
    Quality,
    Status,
    Usage,
    WorkflowStep,
)
from backend.app.schemas.analytics import Driver, KPIComparison, QueryEvidence, Row

STEPS = {
    "interpret": "Interpret question",
    "validate": "Validate analytical intent",
    "definition": "Retrieve KPI definition",
    "plan": "Create analysis plan",
    "select": "Select approved tools",
    "execute": "Execute read-only SQL",
    "quality": "Validate data quality",
    "verify": "Verify analytical evidence",
    "answer": "Generate grounded answer",
}


class State(TypedDict, total=False):
    question: str
    status: Status
    summary: str
    plan: Plan
    definition: dict[str, str]
    query_ids: list[str]
    evidence: list[QueryEvidence]
    comparison: KPIComparison
    drivers: list[Driver]
    quality: Quality
    findings: list[Finding]
    supporting: list[Row]
    chart: Chart | None
    caveats: list[str]
    steps: list[WorkflowStep]
    usage: Usage | None
