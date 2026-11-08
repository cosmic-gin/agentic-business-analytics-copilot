import csv
import json
from pathlib import Path

import yaml
from pydantic import TypeAdapter

from backend.app.core.config import ROOT
from backend.app.db.queries import DIMENSIONS
from backend.app.db.reader import AnalyticsReader
from backend.app.schemas.analytics import (
    Dimension,
    Driver,
    KPIComparison,
    Metric,
    QueryEvidence,
    Scope,
)

DATASET = json.loads((ROOT / "data/metadata/dataset.json").read_text(encoding="utf-8"))
KPI_DEFINITIONS = yaml.safe_load(
    (ROOT / "data/metadata/kpi_definitions.yaml").read_text(encoding="utf-8")
)
RATES = {"on_time_rate", "late_rate"}


def _filter_catalog():
    snapshot = ROOT / "data" / "snapshot" / DATASET["version"]
    catalog = {}
    for dimension, (table, id_key, label_key) in DIMENSIONS.items():
        with (snapshot / f"{table}.csv").open(encoding="utf-8", newline="") as stream:
            catalog[f"{dimension}_id"] = {int(row[id_key]): row[label_key] for row in csv.DictReader(stream)}
    return catalog


FILTER_CATALOG = _filter_catalog()


class AnalyticsTools:
    def __init__(self, database: Path):
        self.reader = AnalyticsReader(database)

    def get_kpi_definition(self, metric: Metric) -> dict[str, str]:
        return KPI_DEFINITIONS["metrics"][TypeAdapter(Metric).validate_python(metric)]

    def get_available_dimensions(self) -> dict[Dimension, QueryEvidence]:
        return {dimension: self.reader.run(f"{dimension}_values", {})
                for dimension in ("category", "warehouse", "carrier")}

    def _scoped(self, query_id: str, scope: Scope) -> QueryEvidence:
        return self.reader.run(query_id, {**scope.model_dump(), "cutoff": DATASET["cutoff_exclusive"]})

    def get_monthly_kpi(self, scope: Scope) -> QueryEvidence:
        return self._scoped("monthly_kpi", scope)

    def overview(self) -> QueryEvidence:
        return self._scoped("overview", Scope(start=DATASET["first_month"], end=DATASET["latest_month"]))

    def compare_kpi_periods(self, scope: Scope, metric: Metric) -> tuple[KPIComparison, QueryEvidence]:
        metric = TypeAdapter(Metric).validate_python(metric)
        evidence = self.get_monthly_kpi(scope)
        periods = {row["period"]: row for row in evidence.rows}
        previous, current = periods.get(scope.start, {}), periods.get(scope.end, {})
        before, after = previous.get(metric), current.get(metric)
        if metric not in RATES:
            before, after = before or 0, after or 0
        comparison = KPIComparison(
            previous_period=scope.start, current_period=scope.end,
            previous_value=before, current_value=after,
            previous_valid=previous.get("valid_deliveries", 0),
            current_valid=current.get("valid_deliveries", 0),
            previous_late=previous.get("late_deliveries", 0),
            current_late=current.get("late_deliveries", 0),
            change_pp=round(after - before, 9) if metric in RATES and before is not None
            and after is not None else None,
        )
        return comparison, evidence

    def get_breakdown(self, dimension: Dimension, scope: Scope) -> QueryEvidence:
        dimension = TypeAdapter(Dimension).validate_python(dimension)
        return self._scoped(f"{dimension}_breakdown", scope)

    def get_category_breakdown(self, scope: Scope) -> QueryEvidence:
        return self.get_breakdown("category", scope)

    def get_warehouse_breakdown(self, scope: Scope) -> QueryEvidence:
        return self.get_breakdown("warehouse", scope)

    def get_carrier_breakdown(self, scope: Scope) -> QueryEvidence:
        return self.get_breakdown("carrier", scope)

    def check_data_quality(self, scope: Scope) -> QueryEvidence:
        return self._scoped("data_quality", scope)


def category_drivers(comparison: KPIComparison, evidence: QueryEvidence) -> list[Driver]:
    rows = {(row["period"], row["name"]): row for row in evidence.rows}
    names = sorted({row["name"] for row in evidence.rows})
    drivers = []
    for name in names:
        before = rows.get((comparison.previous_period, name), {})
        after = rows.get((comparison.current_period, name), {})
        previous_late, current_late = before.get("late_deliveries", 0), after.get("late_deliveries", 0)
        previous_valid, current_valid = before.get("valid_deliveries", 0), after.get("valid_deliveries", 0)
        previous_rate, current_rate = before.get("late_rate"), after.get("late_rate")
        contribution = within = mix = None
        if comparison.previous_valid and comparison.current_valid:
            contribution = 100 * (
                current_late / comparison.current_valid - previous_late / comparison.previous_valid
            )
            if previous_rate is not None and current_rate is not None:
                previous_share = previous_valid / comparison.previous_valid
                current_share = current_valid / comparison.current_valid
                within = (current_rate - previous_rate) * (previous_share + current_share) / 2
                mix = (current_share - previous_share) * (previous_rate + current_rate) / 2
        drivers.append(Driver(
            category=name, previous_valid=previous_valid, current_valid=current_valid,
            previous_late=previous_late, current_late=current_late,
            late_count_change=current_late - previous_late, previous_late_rate=previous_rate,
            current_late_rate=current_rate, late_rate_contribution_pp=contribution,
            within_category_effect_pp=within, category_mix_effect_pp=mix,
        ))
    return sorted(drivers, key=lambda driver: (-driver.late_count_change, driver.category))
