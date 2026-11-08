CREATE TABLE product_categories (
    product_category_id INTEGER PRIMARY KEY,
    category_name TEXT NOT NULL UNIQUE
);
CREATE TABLE warehouses (
    warehouse_id INTEGER PRIMARY KEY,
    warehouse_name TEXT NOT NULL UNIQUE,
    region TEXT NOT NULL
);
CREATE TABLE carriers (
    carrier_id INTEGER PRIMARY KEY,
    carrier_name TEXT NOT NULL UNIQUE
);
CREATE TABLE shipments (
    order_id TEXT PRIMARY KEY NOT NULL,
    order_date TEXT NOT NULL,
    promised_delivery_at TEXT,
    actual_delivery_at TEXT,
    product_category_id INTEGER NOT NULL REFERENCES product_categories,
    warehouse_id INTEGER NOT NULL REFERENCES warehouses,
    carrier_id INTEGER NOT NULL REFERENCES carriers,
    order_value REAL NOT NULL CHECK (order_value >= 0),
    delivery_status TEXT NOT NULL CHECK (delivery_status IN ('completed', 'pending', 'cancelled')),
    reporting_month TEXT GENERATED ALWAYS AS (substr(coalesce(promised_delivery_at, order_date), 1, 7)) STORED,
    CHECK (promised_delivery_at IS NULL OR promised_delivery_at >= order_date),
    CHECK (actual_delivery_at IS NULL OR actual_delivery_at >= order_date),
    CHECK (delivery_status = 'completed' OR actual_delivery_at IS NULL)
);
CREATE INDEX shipments_month ON shipments(reporting_month);
CREATE INDEX shipments_category ON shipments(product_category_id);
CREATE INDEX shipments_warehouse ON shipments(warehouse_id);
CREATE INDEX shipments_carrier ON shipments(carrier_id);
