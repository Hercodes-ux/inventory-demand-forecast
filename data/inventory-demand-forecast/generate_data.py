"""Generate a synthetic, seeded dataset for Project 2.

Models a small distribution operation: 20 SKUs across 3 warehouses,
12 months of daily demand (2026-01-01 to 2026-12-31) with trend,
weekly seasonality, annual seasonality for two SKUs, random noise,
one promotional demand spike, one discontinued SKU, and one very
slow-moving SKU.

Outputs (data/):
  products.csv           - one row per SKU: cost, lead time, reorder point, ...
  demand_daily.csv       - one row per SKU per day: units demanded
  inventory_daily.csv    - simulated daily inventory ledger per SKU
  inventory_snapshot.csv - final-day on-hand per SKU

The data is SIMULATED (fixed seed, reproducible). It is not real
company data. The analysis methods are the demonstration.

Regenerate with:  python generate_data.py
"""

import csv
import math
import os
from datetime import date, timedelta

import numpy as np

SEED = 42
START = date(2026, 1, 1)
DAYS = 365
BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "data")

# sku_id, name, category, warehouse, base daily demand, weekend factor,
# trend over the year (+0.15 = +15%), seasonal pattern, special flag,
# unit cost ($), supplier lead time (days)
SKUS = [
    ("SKU-101", "Ceramic Mug 12 oz", "Home Goods", "Cleveland", 38, 1.20, 0.10, None, None, 8.50, 7),
    ("SKU-102", "Stainless Steel Water Bottle 750ml", "Home Goods", "Cleveland", 45, 1.25, 0.15, None, None, 14.99, 5),
    ("SKU-103", "Cotton Bath Towel Set", "Home Goods", "Cleveland", 22, 1.20, 0.05, None, None, 24.00, 10),
    ("SKU-104", "LED Desk Lamp", "Home Goods", "Cleveland", 18, 1.15, -0.05, None, None, 32.50, 14),
    ("SKU-105", "Electric Kettle 1.7L", "Small Appliances", "Cleveland", 15, 1.10, 0.05, "winter", None, 27.99, 7),
    ("SKU-106", "Yoga Mat", "Sporting Goods", "Cleveland", 26, 1.30, 0.20, "summer", None, 19.99, 10),
    ("SKU-201", "Wireless Mouse", "Electronics Accessories", "Columbus", 55, 1.10, 0.12, None, "promo", 16.49, 21),
    ("SKU-202", "USB-C Charging Cable 6ft", "Electronics Accessories", "Columbus", 62, 1.10, 0.08, None, None, 9.99, 5),
    ("SKU-203", "Bluetooth Speaker Mini", "Electronics Accessories", "Columbus", 30, 1.25, -0.10, None, "discontinued", 22.99, 14),
    ("SKU-204", "Laptop Stand Adjustable", "Electronics Accessories", "Columbus", 12, 1.15, 0.10, None, None, 34.99, 10),
    ("SKU-205", "Resistance Band Set", "Sporting Goods", "Columbus", 20, 1.30, 0.05, None, None, 15.99, 7),
    ("SKU-206", "Handheld Vacuum", "Small Appliances", "Columbus", 9, 1.10, 0.00, None, None, 42.00, 21),
    ("SKU-301", "Ballpoint Pen Box (24)", "Office Supplies", "Chicago", 48, 0.55, 0.05, None, None, 6.25, 3),
    ("SKU-302", "A4 Notebook Pack (3)", "Office Supplies", "Chicago", 34, 0.55, 0.10, None, None, 11.50, 5),
    ("SKU-303", "Desk Organizer Tray", "Office Supplies", "Chicago", 16, 0.55, -0.05, None, None, 13.75, 7),
    ("SKU-304", "Whiteboard Marker Set", "Office Supplies", "Chicago", 11, 0.55, 0.00, None, None, 8.99, 10),
    ("SKU-305", "Cardboard Mailer Box S", "Packaging", "Chicago", 58, 0.60, 0.18, None, None, 4.80, 5),
    ("SKU-306", "Bubble Wrap Roll", "Packaging", "Chicago", 28, 0.60, 0.05, None, None, 12.40, 7),
    ("SKU-307", "Packing Tape 6-Pack", "Packaging", "Chicago", 40, 0.60, 0.10, None, None, 7.60, 3),
    ("SKU-308", "Specialty Label Roll", "Packaging", "Chicago", 0.35, 0.60, 0.00, None, "slow", 18.30, 14),
]

PROMO_START_DAY = 210  # 2026-07-30, 3-week promotion on SKU-201
PROMO_LENGTH_DAYS = 21
PROMO_MULTIPLIER = 2.2
DISCONTINUED_AFTER_DAY = 270  # 2026-09-28: SKU-203 demand stops


def seasonal_factor(pattern, day_of_year):
    """Annual seasonality: winter peaks mid-January, summer peaks mid-July."""
    if pattern == "winter":
        return max(0.2, 1.0 + 0.45 * math.cos(2 * math.pi * (day_of_year - 15) / 365))
    if pattern == "summer":
        return max(0.2, 1.0 + 0.45 * math.cos(2 * math.pi * (day_of_year - 196) / 365))
    return 1.0


def main():
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(SEED)
    dates = [START + timedelta(days=i) for i in range(DAYS)]

    # --- Step 1: generate daily demand per SKU -------------------------
    demand = {}  # sku_id -> list of 365 daily demands
    for sku in SKUS:
        (sku_id, _name, _cat, _wh, base, weekend_factor, trend,
         pattern, special, _cost, _lead) = sku
        series = []
        for i, d in enumerate(dates):
            if special == "discontinued" and i >= DISCONTINUED_AFTER_DAY:
                series.append(0)
                continue
            lam = base * (1.0 + trend * i / DAYS)
            if d.weekday() >= 5:  # Saturday / Sunday
                lam *= weekend_factor
            lam *= seasonal_factor(pattern, d.timetuple().tm_yday)
            if special == "promo" and PROMO_START_DAY <= i < PROMO_START_DAY + PROMO_LENGTH_DAYS:
                lam *= PROMO_MULTIPLIER
            series.append(int(rng.poisson(max(lam, 0.0))))
        demand[sku_id] = series

    # --- Step 2: reorder policy per SKU (from the generated demand) ----
    # reorder point = average daily demand x lead time x 1.25 (safety buffer)
    # order-up-to level = average daily demand x (lead time + 14 days)
    # starting on-hand = ~25 days of base demand (10 days for the promo SKU,
    # which starts the year tight and is the designed stockout case)
    products = []
    for sku in SKUS:
        (sku_id, name, cat, wh, base, _wf, _tr, _pat, special,
         cost, lead) = sku
        avg_daily = float(np.mean(demand[sku_id]))
        reorder_point = max(10, int(math.ceil(avg_daily * lead * 1.25)))
        order_up_to = int(math.ceil(avg_daily * (lead + 14)))
        cover_days = 10 if special == "promo" else 25
        starting = int(round(base * cover_days))
        products.append({
            "sku_id": sku_id, "sku_name": name, "category": cat,
            "warehouse": wh, "unit_cost": cost, "lead_time_days": lead,
            "reorder_point": reorder_point, "order_up_to_level": order_up_to,
            "starting_on_hand": starting,
        })

    # --- Step 3: simulate daily inventory per SKU ----------------------
    # Each day: arrivals land, demand is filled from stock, unfilled demand
    # is lost (a stockout), and an order is placed only when the inventory
    # POSITION (on-hand + already on order) falls below the reorder point.
    # Ordering on position, not on-hand alone, is what stops duplicate
    # orders from piling up while a replenishment is already in transit.
    # A stockout day = end-of-day on-hand <= 0.
    demand_rows = []
    inventory_rows = []
    snapshot_rows = []
    for p in products:
        sku_id = p["sku_id"]
        lead = p["lead_time_days"]
        on_hand = p["starting_on_hand"]
        pending = []  # list of (arrival_date, qty)
        for i, d in enumerate(dates):
            due_today = sum(q for (ad, q) in pending if ad == d)
            pending = [(ad, q) for (ad, q) in pending if ad != d]
            on_hand_start = on_hand + due_today
            dem = demand[sku_id][i]
            fulfilled = min(dem, on_hand_start)
            on_hand_end = on_hand_start - fulfilled
            in_transit = sum(q for (ad, q) in pending)
            order_qty = 0
            if on_hand_end + in_transit < p["reorder_point"]:
                order_qty = p["order_up_to_level"] - (on_hand_end + in_transit)
                pending.append((d + timedelta(days=lead), order_qty))
            demand_rows.append([d.isoformat(), sku_id, p["warehouse"], dem])
            inventory_rows.append([d.isoformat(), sku_id, p["warehouse"],
                                   on_hand_start, dem, fulfilled,
                                   on_hand_end, order_qty])
            on_hand = on_hand_end
        snapshot_rows.append([dates[-1].isoformat(), sku_id, p["warehouse"],
                              on_hand, p["reorder_point"], p["unit_cost"],
                              round(on_hand * p["unit_cost"], 2)])

    def write_csv(path, header, rows):
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)

    write_csv(os.path.join(OUT, "products.csv"),
              ["sku_id", "sku_name", "category", "warehouse", "unit_cost",
               "lead_time_days", "reorder_point", "order_up_to_level",
               "starting_on_hand"],
              [[p["sku_id"], p["sku_name"], p["category"], p["warehouse"],
                p["unit_cost"], p["lead_time_days"], p["reorder_point"],
                p["order_up_to_level"], p["starting_on_hand"]] for p in products])
    write_csv(os.path.join(OUT, "demand_daily.csv"),
              ["date", "sku_id", "warehouse", "units_demanded"], demand_rows)
    write_csv(os.path.join(OUT, "inventory_daily.csv"),
              ["date", "sku_id", "warehouse", "on_hand_start", "demand",
               "fulfilled", "on_hand_end", "order_placed_qty"], inventory_rows)
    write_csv(os.path.join(OUT, "inventory_snapshot.csv"),
              ["date", "sku_id", "warehouse", "on_hand", "reorder_point",
               "unit_cost", "on_hand_value"], snapshot_rows)

    print(f"SKUs: {len(products)}, days: {DAYS}, "
          f"demand rows: {len(demand_rows)}, inventory rows: {len(inventory_rows)}")
    print(f"Total demand: {sum(sum(v) for v in demand.values()):,} units")


if __name__ == "__main__":
    main()
