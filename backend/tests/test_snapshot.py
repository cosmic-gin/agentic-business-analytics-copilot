import sqlite3
from contextlib import closing

from scripts.build_database import build_database
from scripts.generate_snapshot import SNAPSHOT, generate


def test_snapshot_reproduces_bytes(tmp_path, database):
    generate(tmp_path)
    for source in SNAPSHOT.glob("*.csv"):
        assert (tmp_path / source.name).read_bytes() == source.read_bytes()
    rebuilt = tmp_path / "rebuilt.sqlite"
    build_database(rebuilt, tmp_path)
    assert rebuilt.read_bytes() == database.read_bytes()


def test_baseline_and_integrity(database):
    with closing(sqlite3.connect(database)) as db:
        assert db.execute("SELECT count(*) FROM shipments").fetchone()[0] == 12_275
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        assert db.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        baseline = db.execute("""
            SELECT substr(promised_delivery_at, 1, 7), count(*),
                   sum(actual_delivery_at <= promised_delivery_at)
            FROM shipments
            WHERE delivery_status = 'completed'
              AND actual_delivery_at IS NOT NULL AND promised_delivery_at IS NOT NULL
              AND substr(promised_delivery_at, 1, 7) IN ('2026-04', '2026-05')
            GROUP BY 1 ORDER BY 1
        """).fetchall()
        driver = db.execute("""
            SELECT category_name,
                   sum(CASE WHEN substr(promised_delivery_at, 1, 7) = '2026-05' THEN 1 ELSE -1 END)
            FROM shipments JOIN product_categories USING (product_category_id)
            WHERE delivery_status = 'completed' AND actual_delivery_at > promised_delivery_at
              AND substr(promised_delivery_at, 1, 7) IN ('2026-04', '2026-05')
            GROUP BY category_name ORDER BY 2 DESC, 1
        """).fetchall()
        print("Baseline:", baseline, "Late count changes:", driver)
        assert baseline == [("2026-04", 1000, 940), ("2026-05", 1000, 910)]
        assert driver[0] == ("Safety & Control", 27)
        assert driver[0][1] > driver[1][1]
