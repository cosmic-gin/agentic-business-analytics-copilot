import calendar
import re
from typing import Protocol

from backend.app.schemas.agent import Plan, Status, Usage
from backend.app.schemas.analytics import MONTH, Dimension, Metric, Scope
from backend.app.services.analytics import DATASET, FILTER_CATALOG

MONTHS = {name.lower(): i for names in (calendar.month_name, calendar.month_abbr)
          for i, name in enumerate(names) if i}
MONTH_PATTERN = re.compile(
    r"(?<!\w)(?:(?P<iso>20\d{2}-\d{2})|(?P<name>"
    + "|".join(sorted(MONTHS, key=len, reverse=True))
    + r")\b(?:[ ,]+(?P<year>20\d{2}))?)(?!\w)"
)
LATEST_PERIOD = re.compile(r"\b(latest|last completed|most recent)\b", re.IGNORECASE)
METRIC_PHRASES: tuple[tuple[Metric, str], ...] = (
    ("late_rate", r"\blate[ -](?:delivery |deliveries )?rate\b"),
    ("on_time_rate", r"\bon[ -]time\b"),
    ("valid_deliveries", r"\b(volume|valid deliveries|completed deliveries|total deliveries)\b"),
    ("late_deliveries", r"\b(late deliveries|late orders|late shipments)\b"),
)
DIMENSION_PHRASES: tuple[tuple[Dimension, str], ...] = (
    ("category", r"\bcategor(?:y|ies)\b"), ("warehouse", r"\bwarehouses?\b"), ("carrier", r"\bcarriers?\b"),
)
UNSAFE = re.compile(
    r"\b(delete|truncate|insert|alter|attach|detach|pragma|grant|revoke|load_extension|vacuum|"
    r"sqlite_master|sqlite_schema|secrets?|passwords?|api[ _-]?keys?|credentials?|system prompt)\b"
    r"|\bdrop\s+(?:all\s+|the\s+)?(?:tables?|indexes?|views?|triggers?|databases?|schemas?)\b"
    r"|\bcreate\s+(?:temp(?:orary)?\s+|virtual\s+)?(?:table|index|view|trigger)\b"
    r"|\breplace\s+into\b"
    r"|\bupdate\b.*\b(table|records?|database|orders?|shipments?)\b"
    r"|\b(ignore|bypass|override|disregard)\b.*\b(instructions?|security|rules?|restrictions?|permissions?)\b"
    r"|\bselect\b.*\bfrom\b|--|/\*"
)
OUTSIDE = r"\b(revenue|profit|sales|margin|customers?|refunds?|inventory|forecast|predict|weather|marketing|pricing|satisfaction|root cause)\b"
CREDENTIAL_SHAPE = re.compile(r"\b(?:sk-|gsk_|gh[pousr]_|github_pat_)[A-Za-z0-9_-]{20,}")


class PlanningIssue(Exception):
    def __init__(self, status: Status, message: str, usage: Usage | None = None):
        super().__init__(message)
        self.status = status
        self.usage = usage


class Planner(Protocol):
    def interpret(self, question: str) -> tuple[Plan, Usage | None]: ...


def guard_question(question: str):
    if UNSAFE.search(" ".join(question.lower().split())) or CREDENTIAL_SHAPE.search(question):
        raise PlanningIssue("rejected", "This assistant can run approved read-only delivery analyses. "
                            "Database changes, raw SQL and secrets are outside its permissions.")


def previous_month(month: str) -> str:
    year, index = map(int, month.split("-"))
    return f"{year - 1}-12" if index == 1 else f"{year}-{index - 1:02d}"


def named_month(match: re.Match, year: str) -> str:
    return match["iso"] or f"{match['year'] or year}-{MONTHS[match['name']]:02d}"


def requested_metrics(question: str) -> list[Metric]:
    return [metric for metric, pattern in METRIC_PHRASES if re.search(pattern, question, re.IGNORECASE)]


def requested_dimensions(question: str) -> list[Dimension]:
    return [dimension for dimension, pattern in DIMENSION_PHRASES if re.search(pattern, question, re.IGNORECASE)]


def mentions_member(question: str, label: str) -> bool:
    def words(value: str) -> str:
        return " " + " ".join(re.findall(r"\w+", value.casefold().replace("&", " and "))) + " "

    return bool(label) and words(label) in words(question)


def validate_plan(plan: Plan) -> Plan:
    scope = plan.scope
    if scope.start < DATASET["first_month"] or scope.end > DATASET["latest_month"]:
        raise PlanningIssue("unsupported", f"The simulated snapshot covers {DATASET['first_month']} "
                            f"through {DATASET['latest_month']}. Choose a month within that range.")
    if plan.intent in {"compare", "drivers"} and scope.start == scope.end:
        raise PlanningIssue("ambiguous", "Which two distinct reporting months should I compare?")
    if plan.intent in {"monthly", "breakdown"} and scope.start != scope.end:
        raise PlanningIssue("ambiguous", "Choose one reporting month for this analysis.")
    if plan.intent == "breakdown" and plan.dimension is None:
        raise PlanningIssue("ambiguous", "Choose category, warehouse or carrier.")
    filters = scope.model_dump()
    if any(filters[field] is not None and filters[field] not in members
           for field, members in FILTER_CATALOG.items()):
        raise PlanningIssue("unsupported", "Choose a category, warehouse or carrier in the snapshot.")
    if (plan.intent == "drivers" and scope.category_id is not None) or (
        plan.intent == "breakdown" and filters[f"{plan.dimension}_id"] is not None
    ):
        raise PlanningIssue("ambiguous", "Ask for a comparison within that group or a breakdown across groups.")
    if plan.intent != "breakdown" and plan.dimension is not None:
        raise PlanningIssue("ambiguous", "Ask for a period comparison or one breakdown dimension.")
    return plan


class DeterministicPlanner:
    def interpret(self, question: str) -> tuple[Plan, None]:
        q = question.lower()
        if re.search(OUTSIDE, q) or re.search(r"\border\s+\S*\d", q):
            raise PlanningIssue("unsupported", "This dataset supports aggregate shipment delivery KPIs and data quality.")
        if any(mentions_member(q, label) for members in FILTER_CATALOG.values() for label in members.values()):
            raise PlanningIssue("unsupported", "Named category, warehouse and carrier filters are available in LLM mode.")
        found = list(MONTH_PATTERN.finditer(q))
        years = set(re.findall(r"\b20\d{2}\b", q))
        if len(years) > 1 or years and not found:
            raise PlanningIssue("unsupported", "Use a month in the January through October 2026 snapshot.")
        year = next(iter(years), DATASET["latest_month"][:4])
        periods = sorted({named_month(match, year) for match in found})
        if any(not re.fullmatch(MONTH, period) or not DATASET["first_month"] <= period <= DATASET["latest_month"]
               for period in periods):
            raise PlanningIssue("unsupported", "Use a month in the January through October 2026 snapshot.")
        if len(periods) > 2:
            raise PlanningIssue("ambiguous", "Specify at most two reporting months.")
        dimensions = requested_dimensions(q)
        if len(dimensions) > 1:
            raise PlanningIssue("ambiguous", "Choose one breakdown dimension per question.")
        dimension = next(iter(dimensions), None)
        latest = DATASET["latest_month"]
        metrics = requested_metrics(q)
        if metrics:
            metric = metrics[0]
        elif dimension in {"warehouse", "carrier"}:
            metric = "late_rate"
        elif dimension == "category":
            metric = "late_deliveries"
        else:
            metric = "on_time_rate"

        end = periods[-1] if periods else latest
        start = periods[0] if periods else end
        if re.search(r"\b(missing|incomplete|excluded|exclusions?|data quality|completeness|pending|cancelled)\b", q):
            intent = "quality"
        elif re.search(r"\b(trend|over time|month.by.month)\b", q) and not dimension:
            intent = "trend"
            start = periods[0] if len(periods) == 2 else DATASET["first_month"]
        elif re.search(r"\b(why|deteriorat\w*|declin\w*|decreas\w*|drop(?:s|ped)?|contribut\w*|driver\w*)\b", q):
            if dimension in {"carrier", "warehouse"} or not (dimension or re.search(r"deliver|on[ -]time|late", q)):
                raise PlanningIssue("unsupported", "Ask about delivery KPI changes or category contributions.")
            intent = "drivers"
            start = periods[0] if len(periods) == 2 else previous_month(end)
            if metric == "late_deliveries":
                metric = "late_rate"
        elif len(periods) == 2 or re.search(r"\b(compare|comparison|versus|change[ds]?)\b", q):
            if dimension:
                raise PlanningIssue("unsupported", "Ask for a single-month breakdown or an overall month comparison.")
            if not periods:
                raise PlanningIssue("ambiguous", "Specify the reporting months to compare.")
            intent = "compare"
            start = periods[0] if len(periods) == 2 else previous_month(end)
        elif dimension:
            intent = "breakdown"
        elif re.search(r"\b(on[ -]time|late|delivery performance|deliveries|delivery volume)\b", q):
            if not periods and not LATEST_PERIOD.search(q):
                raise PlanningIssue("ambiguous", "Which reporting month should I use? You can also ask for the latest month.")
            intent = "monthly"
        else:
            status = "ambiguous" if re.search(r"\b(performance|how did|kpi|may|compare)\b", q) else "unsupported"
            raise PlanningIssue(status, "Ask for a delivery KPI, comparison, trend, breakdown or data quality check.")
        lower = bool(re.search(r"\b(lowest|fewest|best)\b", q))
        if metric == "on_time_rate" and re.search(r"\b(best|worst)\b", q):
            lower = bool(re.search(r"\bworst\b", q))
        return Plan(intent=intent, metric=metric, scope=Scope(start=start, end=end),
                    dimension=dimension if intent == "breakdown" else None,
                    ranking="lowest" if lower else "highest"), None
