import csv
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET = json.loads((ROOT / "data/metadata/dataset.json").read_text(encoding="utf-8"))
SNAPSHOT = ROOT / "data" / "snapshot" / DATASET["version"]
DIMENSIONS = {
    "product_categories": [
        ("product_category_id", "category_name"),
        (1, "Safety & Control"), (2, "Fasteners"), (3, "Electrical"),
        (4, "Packaging"), (5, "Tools"),
    ],
    "warehouses": [
        ("warehouse_id", "warehouse_name", "region"),
        (1, "Berlin DC", "Central"), (2, "Hamburg DC", "North"),
        (3, "Munich DC", "South"), (4, "Cologne DC", "West"),
    ],
    "carriers": [
        ("carrier_id", "carrier_name"),
        (1, "Atlas Freight"), (2, "Meridian Parcel"), (3, "Northline Logistics"),
    ],
}
SHIPMENT_COLUMNS = (
    "order_id", "order_date", "promised_delivery_at", "actual_delivery_at",
    "product_category_id", "warehouse_id", "carrier_id", "order_value", "delivery_status",
)


def utc(value: datetime | None) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ") if value is not None else ""


def shipments():
    rng = random.Random(DATASET["seed"])
    # Per-category (valid volume, late count), with a May mix shift.
    controls = {
        4: [(200, 12), (240, 15), (210, 12), (180, 10), (170, 11)],
        5: [(240, 39), (210, 16), (200, 12), (180, 12), (170, 11)],
    }
    for month in range(1, 11):
        sequence = 0
        for category in range(1, 6):
            volume, late_count = controls.get(month, [(250, 0)] * 5)[category - 1]
            controlled_late = set(rng.sample(range(volume), late_count))
            scenarios = (
                ["valid"] * volume + ["missing_actual"] * 2 + ["missing_promise"]
                + ["cancelled"] * 2 + (["pending"] * 5 if month == 10 else [])
            )
            for index, scenario in enumerate(scenarios):
                sequence += 1
                promised = datetime(2026, month, rng.randint(5, 24), 18, tzinfo=timezone.utc)
                ordered = promised - timedelta(days=rng.randint(2, 4), hours=8)
                warehouse = rng.choices(range(1, 5), weights=[4, 3, 3, 2])[0]
                carrier = rng.choices(range(1, 4), weights=[5, 4, 3])[0]
                late = index in controlled_late if month in controls else (
                    rng.random() < 0.025 + category * 0.006 + carrier * 0.009
                    + warehouse * 0.004 + (0.02 if month in {8, 10} else 0)
                )
                offset = rng.randint(1, 96) if late else -rng.randint(0, 30)
                actual = promised + timedelta(hours=offset)
                if scenario in {"missing_actual", "cancelled", "pending"}:
                    actual = None
                status = scenario if scenario in {"cancelled", "pending"} else "completed"
                yield (
                    f"ORD-2026{month:02d}-{sequence:04d}", utc(ordered),
                    utc(None if scenario == "missing_promise" else promised), utc(actual),
                    category, warehouse, carrier, f"{rng.randint(900, 230000) / 100:.2f}", status,
                )


def generate(destination: Path = SNAPSHOT):
    destination.mkdir(parents=True, exist_ok=True)
    for name, rows in DIMENSIONS.items():
        with (destination / f"{name}.csv").open("w", encoding="utf-8", newline="") as stream:
            csv.writer(stream, lineterminator="\n").writerows(rows)
    with (destination / "shipments.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(SHIPMENT_COLUMNS)
        writer.writerows(shipments())


if __name__ == "__main__":
    generate()
    print(f"Generated simulated snapshot {DATASET['version']}")
