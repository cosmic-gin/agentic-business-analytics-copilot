import argparse
import csv
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from tempfile import NamedTemporaryFile

from scripts.generate_snapshot import DIMENSIONS, ROOT, SHIPMENT_COLUMNS, SNAPSHOT


def build_database(destination: Path, snapshot: Path = SNAPSHOT):
    destination.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=destination.parent, suffix=".sqlite", delete=False) as file:
        temporary = Path(file.name)
    try:
        with closing(sqlite3.connect(temporary)) as db, db:
            db.execute("PRAGMA foreign_keys = ON")
            db.executescript((ROOT / "backend/app/db/schema.sql").read_text(encoding="utf-8"))
            tables = {name: rows[0] for name, rows in DIMENSIONS.items()}
            tables["shipments"] = SHIPMENT_COLUMNS
            for table, columns in tables.items():
                with (snapshot / f"{table}.csv").open(encoding="utf-8", newline="") as stream:
                    reader = csv.reader(stream)
                    if tuple(next(reader)) != columns:
                        raise ValueError(f"Unexpected CSV header for {table}")
                    bindings = ", ".join("?" for _ in columns)
                    db.executemany(
                        f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({bindings})",
                        (tuple(value or None for value in row) for row in reader),
                    )
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build SQLite from the versioned simulated snapshot.")
    parser.add_argument("--output", type=Path, default=ROOT / "data/analytics.sqlite")
    args = parser.parse_args()
    build_database(args.output)
    print(f"Built {args.output}")
