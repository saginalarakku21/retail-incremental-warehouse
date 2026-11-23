import tempfile
import unittest
from pathlib import Path

import duckdb

from pipeline import load


class WarehouseTest(unittest.TestCase):
    def test_late_dimension_changes_and_replay(self):
        data = Path("data")
        with duckdb.connect() as db, tempfile.TemporaryDirectory() as folder:
            load(db, data / "products_01.csv", data / "orders_01.csv")
            self.assertEqual(db.execute("SELECT category FROM fact_sales WHERE order_id='O2'")
                             .fetchone(), ("Beverages",))
            for _ in range(2):
                load(db, data / "products_02.csv", data / "orders_02.csv")
            expected = [("O1", "Beverages", 500), ("O2", "Energy Drinks", 250),
                        ("O3", "Energy Drinks", 900)]
            query = "SELECT order_id, category, revenue_cents FROM fact_sales ORDER BY order_id"
            self.assertEqual(db.execute(query).fetchall(), expected)
            bad = Path(folder) / "bad.csv"
            bad.write_text("order_id,product_id,order_date,units,revenue_cents\n"
                           "O4,P9,2025-01-05,1,100\n")
            with self.assertRaisesRegex(ValueError, "Missing effective"):
                load(db, data / "products_02.csv", bad)
            bad.write_text("order_id,product_id,order_date,units,revenue_cents\n"
                           "O2,P1,2025-01-04,1,100\n")
            with self.assertRaisesRegex(ValueError, "Conflicting immutable"):
                load(db, data / "products_02.csv", bad)
            self.assertEqual(db.execute(query).fetchall(), expected)
