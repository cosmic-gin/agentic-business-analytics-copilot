import sqlite3

import pytest
from pydantic import ValidationError

from backend.app.db.reader import QueryFailed, authorize
from backend.app.schemas.analytics import Scope
from backend.app.services.analytics import AnalyticsTools, category_drivers

PAIR = Scope(start="2026-04", end="2026-05")


def test_sql_tools(database):
    tools = AnalyticsTools(database)
    comparison, evidence = tools.compare_kpi_periods(PAIR, "on_time_rate")
    assert (comparison.previous_value, comparison.current_value, comparison.change_pp) == (94, 91, -3)
    assert (comparison.previous_late, comparison.current_late) == (60, 90)
    assert evidence.parameters["start"] == "2026-04"
    assert ":start" in evidence.sql
    drivers = category_drivers(comparison, tools.get_category_breakdown(PAIR))
    assert drivers[0].category == "Safety & Control"
    assert drivers[0].late_count_change == 27
    assert sum(d.late_rate_contribution_pp for d in drivers) == pytest.approx(3)
    for driver in drivers:
        assert driver.within_category_effect_pp + driver.category_mix_effect_pp == pytest.approx(
            driver.late_rate_contribution_pp
        )
    quality = tools.check_data_quality(PAIR).rows[0]
    assert (quality["records"], quality["valid_deliveries"]) == (2050, 2000)
    assert (quality["missing_actual"], quality["missing_promise"], quality["cancelled"]) == (20, 10, 20)
    assert set(tools.get_available_dimensions()) == {"category", "warehouse", "carrier"}
    assert tools.get_warehouse_breakdown(PAIR).row_count == 8
    assert tools.get_carrier_breakdown(PAIR).row_count == 6


def test_boundaries_and_empty(database):
    tools = AnalyticsTools(database)
    april = tools.get_monthly_kpi(Scope(start="2026-04", end="2026-04", category_id=1))
    assert [(row["period"], row["valid_deliveries"]) for row in april.rows] == [("2026-04", 200)]
    empty = Scope(start="2027-01", end="2027-02")
    comparison, evidence = tools.compare_kpi_periods(empty, "late_rate")
    assert evidence.rows == [] and comparison.current_value is None
    assert tools.check_data_quality(empty).rows[0]["records"] == 0


@pytest.mark.parametrize("kwargs", [
    {"start": "2026-04' OR 1=1 --"}, {"end": "2026-13"}, {"end": "2025-03"},
    {"end": "2029-05"}, {"category_id": 99}, {"carrier_id": "1; DROP TABLE shipments"},
    {"filter": "anything"},
])
def test_invalid_scope(kwargs):
    with pytest.raises(ValidationError):
        Scope(**({"start": "2026-04", "end": "2026-05"} | kwargs))


def test_invalid_tool_inputs(database):
    tools = AnalyticsTools(database)
    with pytest.raises(ValidationError):
        tools.get_kpi_definition("revenue")
    with pytest.raises(ValidationError):
        tools.get_breakdown("sqlite_master", PAIR)
    with pytest.raises(KeyError):
        tools.reader.run("DROP TABLE shipments", {})


@pytest.mark.parametrize("statement", [
    "DELETE FROM shipments", "DROP TABLE shipments", "UPDATE shipments SET order_value = 0",
    "ATTACH DATABASE ':memory:' AS other", "PRAGMA user_version", "SELECT * FROM sqlite_master",
    "SELECT load_extension('anything')",
])
def test_authorizer_blocks_unsafe_sql(database, statement):
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as db:
        db.set_authorizer(authorize)
        with pytest.raises(sqlite3.DatabaseError):
            db.execute(statement)


def test_database_failure(tmp_path):
    path = tmp_path / "bad.sqlite"
    tools = AnalyticsTools(path)
    with pytest.raises(QueryFailed):
        tools.get_monthly_kpi(PAIR)
    assert not path.exists()
    path.write_text("corrupt")
    with pytest.raises(QueryFailed):
        tools.get_monthly_kpi(PAIR)
