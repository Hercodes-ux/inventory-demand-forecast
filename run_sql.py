"""Load the generated CSVs into SQLite and run every query in sql/.

Outputs land in outputs/ as CSVs with the same base name as the query.
Re-run any time the data is regenerated.

Run with:  python run_sql.py
"""

import csv
import os
import sqlite3

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
SQL = os.path.join(BASE, "sql")
OUT = os.path.join(BASE, "outputs")
DB = os.path.join(DATA, "inventory.db")

QUERIES = [
    ("01_demand_by_sku_warehouse.sql", "demand_by_sku.csv"),
    ("02_stockout_days.sql", "stockout_days.csv"),
    ("03_turnover.sql", "turnover.csv"),
    ("04_days_of_supply.sql", "days_of_supply.csv"),
    ("05_reorder_breaches.sql", "reorder_breaches.csv"),
    ("06_slow_moving.sql", "slow_moving.csv"),
]


def infer_type(values):
    """Pick a SQLite column type from the data: INTEGER, REAL, or TEXT.

    This matters because SQLite only coerces TEXT to numbers for
    arithmetic, not for comparisons (a TEXT '0' is NOT <= the number 0).
    Typing numeric columns keeps the <= / < filters in the queries true.
    """
    non_empty = [v for v in values if v != ""]
    if not non_empty:
        return "TEXT"
    try:
        for v in non_empty:
            int(v)
        return "INTEGER"
    except ValueError:
        pass
    try:
        for v in non_empty:
            float(v)
        return "REAL"
    except ValueError:
        pass
    return "TEXT"


def load_table(conn, path, table):
    with open(path, newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)
    types = [infer_type([r[i] for r in rows]) for i in range(len(header))]
    cols = ", ".join(f'"{c}" {t}' for c, t in zip(header, types))
    conn.execute(f'DROP TABLE IF EXISTS "{table}"')
    conn.execute(f'CREATE TABLE "{table}" ({cols})')
    placeholders = ", ".join("?" * len(header))
    conn.executemany(
        f'INSERT INTO "{table}" VALUES ({placeholders})', rows)
    return len(rows)


def main():
    os.makedirs(OUT, exist_ok=True)
    if os.path.exists(DB):
        os.remove(DB)
    conn = sqlite3.connect(DB)
    for name, table in [("products.csv", "products"),
                        ("demand_daily.csv", "demand_daily"),
                        ("inventory_daily.csv", "inventory_daily"),
                        ("inventory_snapshot.csv", "inventory_snapshot")]:
        n = load_table(conn, os.path.join(DATA, name), table)
        print(f"Loaded {table}: {n} rows")
    for query_file, output_file in QUERIES:
        with open(os.path.join(SQL, query_file)) as f:
            sql = f.read()
        cur = conn.execute(sql)
        columns = [d[0] for d in cur.description]
        rows = cur.fetchall()
        with open(os.path.join(OUT, output_file), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(columns)
            w.writerows(rows)
        print(f"{query_file} -> {output_file} ({len(rows)} rows)")
    conn.close()


if __name__ == "__main__":
    main()
