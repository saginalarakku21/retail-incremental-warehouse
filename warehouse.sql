CREATE TABLE IF NOT EXISTS product_changes (
  product_id VARCHAR NOT NULL, effective_from DATE NOT NULL, category VARCHAR NOT NULL,
  PRIMARY KEY (product_id, effective_from)
);

CREATE TABLE IF NOT EXISTS orders (
  order_id VARCHAR PRIMARY KEY, product_id VARCHAR NOT NULL,
  order_date DATE NOT NULL, units INTEGER NOT NULL CHECK (units > 0),
  revenue_cents BIGINT NOT NULL CHECK (revenue_cents >= 0)
);

CREATE OR REPLACE VIEW dim_product AS
SELECT product_id, category, effective_from,
       lead(effective_from) OVER (PARTITION BY product_id ORDER BY effective_from) AS effective_to
FROM product_changes;

CREATE OR REPLACE VIEW fact_sales AS
SELECT o.*, d.category
FROM orders o
LEFT JOIN dim_product d
  ON o.product_id = d.product_id AND o.order_date >= d.effective_from
  AND (o.order_date < d.effective_to OR d.effective_to IS NULL);

CREATE OR REPLACE VIEW daily_sales AS
SELECT order_date, category, count(*) AS orders, sum(units) AS units,
       sum(revenue_cents) AS revenue_cents
FROM fact_sales
GROUP BY order_date, category;
