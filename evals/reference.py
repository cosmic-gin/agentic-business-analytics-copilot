"""Independent benchmark truth. This module reads CSV and uses no runtime query code."""
import csv
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
DIMENSIONS = {
    "category": ("product_categories", "product_category_id", "category_name"),
    "warehouse": ("warehouses", "warehouse_id", "warehouse_name"),
    "carrier": ("carriers", "carrier_id", "carrier_name"),
}


class Case(BaseModel):
    id: str
    category: str
    question: str
    status: str
    intent: str | None = None
    start: str | None = None
    end: str | None = None
    metric: str | None = None
    dimension: str | None = None
    ranking: str | None = None
    filters: dict[str, int] = Field(default_factory=dict)


def stamp(value):
    return datetime.fromisoformat(value) if value else None


class Reference:
    def __init__(self):
        self.manifest = json.loads((ROOT / "data/metadata/dataset.json").read_text(encoding="utf-8"))
        self.snapshot = ROOT / "data/snapshot" / self.manifest["version"]
        self.cutoff = stamp(self.manifest["cutoff_exclusive"])
        self.names = {
            dimension: {row[key]: row[label] for row in self.read(table)}
            for dimension, (table, key, label) in DIMENSIONS.items()
        }
        self.shipments = []
        for row in self.read("shipments"):
            promise, actual = stamp(row["promised_delivery_at"]), stamp(row["actual_delivery_at"])
            month = (promise or stamp(row["order_date"])).strftime("%Y-%m")
            self.shipments.append((month, row, promise, actual))

    def read(self, table):
        with (self.snapshot / f"{table}.csv").open(encoding="utf-8", newline="") as source:
            return list(csv.DictReader(source))

    def query_rows(self, case: Case, dimension: str | None = None):
        groups = defaultdict(list)
        quality = dict(records=0, valid_deliveries=0, pending=0, cancelled=0,
                       missing_promise=0, missing_actual=0, after_cutoff=0)
        filters = {DIMENSIONS[field.removesuffix("_id")][1]: str(member)
                   for field, member in case.filters.items()}
        for month, row, promised, actual in self.shipments:
            if not case.start <= month <= case.end or any(row[key] != value for key, value in filters.items()):
                continue
            status = row["delivery_status"]
            quality["records"] += 1
            if status != "completed":
                quality[status] += 1
                continue
            quality["missing_actual"] += actual is None
            quality["missing_promise"] += promised is None
            quality["after_cutoff"] += actual is not None and actual >= self.cutoff
            if promised is None or actual is None or actual >= self.cutoff:
                continue
            quality["valid_deliveries"] += 1
            name = self.names[dimension][row[DIMENSIONS[dimension][1]]] if dimension else ""
            groups[(month, name)].append(actual <= promised)

        rows = []
        for (month, name), decisions in sorted(groups.items()):
            total = len(decisions)
            on_time = decisions.count(True)
            late = decisions.count(False)
            row = dict(period=month, valid_deliveries=total, on_time_deliveries=on_time,
                       late_deliveries=late, on_time_rate=100 * (on_time / total), late_rate=100 * (late / total))
            if dimension:
                row["name"] = name
            rows.append(row)
        return rows, quality
