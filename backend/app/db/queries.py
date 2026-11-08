# These templates are application code. Only bound values reach SQLite from the request.
VALID = """delivery_status = 'completed'
       AND promised_delivery_at IS NOT NULL AND actual_delivery_at IS NOT NULL
       AND actual_delivery_at < :cutoff"""
WINDOW = """reporting_month BETWEEN :start AND :end
       AND (:category_id IS NULL OR product_category_id = :category_id)
       AND (:warehouse_id IS NULL OR warehouse_id = :warehouse_id)
       AND (:carrier_id IS NULL OR carrier_id = :carrier_id)"""
COUNTS = """count(*) AS valid_deliveries,
       sum(actual_delivery_at <= promised_delivery_at) AS on_time_deliveries,
       sum(actual_delivery_at > promised_delivery_at) AS late_deliveries,
       100.0 * sum(actual_delivery_at <= promised_delivery_at) / count(*) AS on_time_rate,
       100.0 * sum(actual_delivery_at > promised_delivery_at) / count(*) AS late_rate"""

DIMENSIONS = {
    "category": ("product_categories", "product_category_id", "category_name"),
    "warehouse": ("warehouses", "warehouse_id", "warehouse_name"),
    "carrier": ("carriers", "carrier_id", "carrier_name"),
}
QUERIES = {
    "health": "SELECT order_id FROM shipments LIMIT 1",
    "monthly_kpi": f"""SELECT reporting_month AS period, {COUNTS}
FROM shipments WHERE {WINDOW} AND {VALID}
GROUP BY reporting_month ORDER BY reporting_month LIMIT :limit""",
    "overview": f"""SELECT {COUNTS}
FROM shipments WHERE {WINDOW} AND {VALID}
HAVING count(*) > 0 LIMIT :limit""",
    "data_quality": f"""SELECT count(*) AS records,
       coalesce(sum(CASE WHEN {VALID} THEN 1 ELSE 0 END), 0) AS valid_deliveries,
       coalesce(sum(delivery_status = 'pending'), 0) AS pending,
       coalesce(sum(delivery_status = 'cancelled'), 0) AS cancelled,
       coalesce(sum(delivery_status = 'completed' AND promised_delivery_at IS NULL), 0) AS missing_promise,
       coalesce(sum(delivery_status = 'completed' AND actual_delivery_at IS NULL), 0) AS missing_actual,
       coalesce(sum(delivery_status = 'completed' AND actual_delivery_at >= :cutoff), 0) AS after_cutoff
FROM shipments WHERE {WINDOW} LIMIT :limit""",
}

for dimension, (table, key, label) in DIMENSIONS.items():
    QUERIES[f"{dimension}_breakdown"] = f"""SELECT reporting_month AS period, {label} AS name,
       {COUNTS}
FROM shipments JOIN {table} USING ({key})
WHERE {WINDOW} AND {VALID}
GROUP BY reporting_month, {label} ORDER BY reporting_month, {label} LIMIT :limit"""
    QUERIES[f"{dimension}_values"] = f"""SELECT {key} AS id, {label} AS name
FROM {table} ORDER BY {key} LIMIT :limit"""

ALLOWED_TABLES = {"shipments", *(value[0] for value in DIMENSIONS.values())}
ALLOWED_FUNCTIONS = {"count", "sum", "coalesce"}
