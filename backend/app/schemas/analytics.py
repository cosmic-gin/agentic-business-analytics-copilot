import re
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Metric = Literal["on_time_rate", "late_rate", "valid_deliveries", "late_deliveries"]
Dimension = Literal["category", "warehouse", "carrier"]
Value = str | int | float | None
Row = dict[str, Value]
MONTH = r"20\d{2}-(?:0[1-9]|1[0-2])"


class Scope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    start: str = Field(pattern=f"^{MONTH}$")
    end: str = Field(pattern=f"^{MONTH}$")
    category_id: Literal[1, 2, 3, 4, 5] | None = None
    warehouse_id: Literal[1, 2, 3, 4] | None = None
    carrier_id: Literal[1, 2, 3] | None = None

    @model_validator(mode="after")
    def bounded_period(self) -> Self:
        def number(month: str) -> int:
            return int(month[:4]) * 12 + int(month[5:])

        if not re.fullmatch(MONTH, self.start) or not re.fullmatch(MONTH, self.end):
            raise ValueError("Use YYYY-MM reporting months.")
        if not 0 <= number(self.end) - number(self.start) < 24:
            raise ValueError("Use an ordered reporting window of at most 24 months.")
        return self


class QueryEvidence(BaseModel):
    query_id: str
    sql: str
    parameters: dict[str, Value]
    rows: list[Row]
    row_count: int
    elapsed_ms: float
    status: Literal["ok"] = "ok"


class KPIComparison(BaseModel):
    previous_period: str
    current_period: str
    previous_value: float | None
    current_value: float | None
    previous_valid: int
    current_valid: int
    previous_late: int
    current_late: int
    change_pp: float | None


class Driver(BaseModel):
    category: str
    previous_valid: int
    current_valid: int
    previous_late: int
    current_late: int
    late_count_change: int
    previous_late_rate: float | None
    current_late_rate: float | None
    late_rate_contribution_pp: float | None
    within_category_effect_pp: float | None
    category_mix_effect_pp: float | None
