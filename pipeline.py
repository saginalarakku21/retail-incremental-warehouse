"""Load immutable sales and effective-dated product changes in one transaction."""
import argparse
from pathlib import Path

import duckdb

SCHEMA = Path(__file__).with_name("warehouse.sql")


def load(connection, products, orders):
    connection.execute(SCHEMA.read_text(encoding="utf-8"))
    connection.begin()
    try:
        connection.execute("""
            CREATE OR REPLACE TEMP TABLE incoming_products AS
            SELECT * FROM read_csv(?, header=true, columns={
               'product_id':'VARCHAR', 'effective_from':'DATE', 'category':'VARCHAR'})
        """, [str(products)])
        connection.execute("""
            CREATE OR REPLACE TEMP TABLE incoming_orders AS
            SELECT * FROM read_csv(?, header=true, columns={
               'order_id':'VARCHAR', 'product_id':'VARCHAR', 'order_date':'DATE',
               'units':'INTEGER', 'revenue_cents':'BIGINT'})
        """, [str(orders)])
        for target, source, keys in (
            ("product_changes", "incoming_products", "product_id, effective_from"),
            ("orders", "incoming_orders", "order_id"),
        ):
            conflict = connection.execute(f"""
                WITH candidates AS (
                    SELECT * FROM {target} UNION SELECT * FROM {source}
                )
                SELECT 1 FROM candidates GROUP BY {keys} HAVING count(*) > 1 LIMIT 1
            """).fetchone()
            if conflict:
                raise ValueError(f"Conflicting immutable records in {target}")
            connection.execute(f"""
                INSERT INTO {target} SELECT DISTINCT * FROM {source} ON CONFLICT DO NOTHING
            """)

        unmatched = connection.execute("""
            SELECT order_id FROM fact_sales WHERE category IS NULL ORDER BY order_id LIMIT 10
        """).fetchall()
        if unmatched:
            raise ValueError(f"Missing effective product version: {unmatched}")
        connection.commit()
    except Exception:
        connection.rollback()
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("products", type=Path)
    parser.add_argument("orders", type=Path)
    parser.add_argument("--db", type=Path, default=Path("output/retail.duckdb"))
    args = parser.parse_args()
    args.db.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(args.db)) as connection:
        load(connection, args.products, args.orders)
        connection.sql("SELECT * FROM daily_sales ORDER BY order_date, category").show()
