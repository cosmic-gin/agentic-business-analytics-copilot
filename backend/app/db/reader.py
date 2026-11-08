import logging
import sqlite3
from contextlib import closing
from pathlib import Path
from time import perf_counter

from backend.app.db.queries import ALLOWED_FUNCTIONS, ALLOWED_TABLES, QUERIES
from backend.app.schemas.analytics import QueryEvidence, Value

logger = logging.getLogger(__name__)
MAX_ROWS = 150
QUERY_TIMEOUT_SECONDS = 1.5


class QueryFailed(RuntimeError):
    pass


def authorize(action, first, second, database, _source):
    if action == sqlite3.SQLITE_SELECT:
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_READ and database == "main" and first in ALLOWED_TABLES:
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_FUNCTION and second in ALLOWED_FUNCTIONS:
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


class AnalyticsReader:
    def __init__(self, path: Path):
        self.path = path.resolve()

    def run(self, query_id: str, parameters: dict[str, Value]) -> QueryEvidence:
        sql = QUERIES[query_id]
        params = {**parameters, "limit": MAX_ROWS + 1}
        started = perf_counter()
        try:
            with closing(sqlite3.connect(
                self.path.as_uri() + "?mode=ro", uri=True, timeout=0.5,
            )) as db:
                db.row_factory = sqlite3.Row
                db.execute("PRAGMA query_only = ON")
                db.execute("PRAGMA trusted_schema = OFF")
                db.set_authorizer(authorize)
                db.set_progress_handler(
                    lambda: int(perf_counter() - started > QUERY_TIMEOUT_SECONDS), 1000,
                )
                rows = [dict(row) for row in db.execute(sql, params).fetchmany(MAX_ROWS + 1)]
                if len(rows) > MAX_ROWS:
                    raise QueryFailed("The query exceeded the evidence row limit.")
        except (sqlite3.Error, QueryFailed) as error:
            logger.warning("analytics_query query_id=%s status=failed", query_id)
            raise QueryFailed("The analytics query could not be completed.") from error
        elapsed_ms = round((perf_counter() - started) * 1000, 2)
        logger.info("analytics_query query_id=%s status=ok rows=%d elapsed_ms=%.2f",
                    query_id, len(rows), elapsed_ms)
        return QueryEvidence(query_id=query_id, sql=sql, parameters=params, rows=rows,
                             row_count=len(rows), elapsed_ms=elapsed_ms)
