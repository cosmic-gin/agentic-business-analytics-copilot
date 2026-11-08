# Database design

The simulated CSV snapshot is versioned under data/snapshot/v1. The fixed seed generates industrial supply shipments across ten complete 2026 reporting months. Build the SQLite database with `python -m scripts.build_database`. The loader checks headers, applies foreign keys, builds in a temporary file and replaces the destination after a successful commit.

| Table | Fields |
| --- | --- |
| shipments | order_id (text primary key), order_date (UTC), promised_delivery_at and actual_delivery_at (nullable UTC), product_category_id, warehouse_id, carrier_id (foreign keys), order_value (USD), delivery_status, reporting_month (generated) |
| product_categories | product_category_id (primary key), category_name |
| warehouses | warehouse_id (primary key), warehouse_name, region |
| carriers | carrier_id (primary key), carrier_name |

Dates use ISO 8601 UTC. Promised delivery month sets the reporting cohort, including shipments arriving after the end of that month. Actual delivery must be before the snapshot cutoff. Pending, cancelled and incomplete completed shipments are excluded from the KPI denominator. Missing promises are attributed to the order month for quality counts. A missing actual and a missing promise can overlap in a general snapshot, so individual defect counts must be read separately from the total excluded count. See the authoritative definitions in data/metadata/kpi_definitions.yaml.
