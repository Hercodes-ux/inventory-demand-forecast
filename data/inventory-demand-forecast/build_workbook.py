"""Build inventory_model.xlsx from the computed SQL + forecast outputs.

Every value comes from outputs/*.csv or data/*.csv — nothing is typed
in by hand. Sheets:
  Inputs & Assumptions, Demand, Forecast, Inventory Health,
  Recommendations (the memo's action table, same numbers).

Run with:  python build_workbook.py
"""

import os
import pandas as pd
from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
OUT = os.path.join(BASE, "outputs")

HEADER_FILL = PatternFill("solid", fgColor="203764")
HEADER_FONT = Font(bold=True, color="FFFFFF")
MONEY_FMT = '"$"#,##0.00'
INT_FMT = '#,##0'
ONE_DEC_FMT = '0.0'
PCT_FMT = '0.0"%"'
RED_FILL = PatternFill("solid", fgColor="FFC7CE")
AMBER_FILL = PatternFill("solid", fgColor="FFEB9C")


def style_header(ws, row, ncols):
    for c in range(1, ncols + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center",
                                   wrap_text=True)


def write_sheet(ws, df, formats=None, widths=None, freeze="A2"):
    """Write a DataFrame to a worksheet with a styled header row."""
    formats = formats or {}
    ws.append(list(df.columns))
    for _, row in df.iterrows():
        ws.append(list(row))
    style_header(ws, 1, len(df.columns))
    for i, col in enumerate(df.columns, start=1):
        fmt = formats.get(col)
        if fmt:
            for r in range(2, len(df) + 2):
                ws.cell(row=r, column=i).number_format = fmt
        if widths and col in widths:
            ws.column_dimensions[get_column_letter(i)].width = widths[col]
    ws.auto_filter.ref = ws.dimensions
    ws.freeze_panes = freeze
    ws.sheet_properties.pageSetUpPr.fitToPage = True


def main():
    prod = pd.read_csv(os.path.join(DATA, "products.csv"))
    dem = pd.read_csv(os.path.join(DATA, "demand_daily.csv"),
                      parse_dates=["date"])
    snap = pd.read_csv(os.path.join(DATA, "inventory_snapshot.csv"))
    demand_by = pd.read_csv(os.path.join(OUT, "demand_by_sku.csv"))
    stockouts = pd.read_csv(os.path.join(OUT, "stockout_days.csv"))
    turnover = pd.read_csv(os.path.join(OUT, "turnover.csv"))
    dos = pd.read_csv(os.path.join(OUT, "days_of_supply.csv"))
    breaches = pd.read_csv(os.path.join(OUT, "reorder_breaches.csv"))
    slow = pd.read_csv(os.path.join(OUT, "slow_moving.csv"))
    fc = pd.read_csv(os.path.join(OUT, "forecast.csv"))

    wb = Workbook()

    # --- Inputs & Assumptions -----------------------------------------
    ws = wb.active
    ws.title = "Inputs & Assumptions"
    inputs = [
        ("Data window", "2026-01-01 to 2026-12-31 (365 days of daily demand)"),
        ("SKUs / warehouses", "20 SKUs across 3 warehouses (Cleveland, Columbus, Chicago)"),
        ("Dataset", "SIMULATED, seeded and reproducible (generate_data.py, seed 42). Not real company data."),
        ("Service level for safety stock", "95% (z = 1.65)"),
        ("Safety stock formula", "1.65 x std. dev. of daily demand x sqrt(lead time in days)"),
        ("Holding-cost assumption", "25% of unit cost per year (context for carrying cost; not used in the order formula)"),
        ("Moving-average forecast", "Mean of the last 30 training days"),
        ("Exponential smoothing", "Simple exponential smoothing, alpha = 0.3"),
        ("Holdout for accuracy", "Last 30 days of the year; MAPE over days with actual demand > 0"),
        ("Chosen forecast per SKU", "The method with the lower holdout MAPE"),
        ("Recommended order quantity", "Forecast demand during lead time + safety stock - on-hand, floored at 0"),
        ("Reorder policy in the simulation", "Order up to order_up_to_level when inventory position (on-hand + on order) falls below the reorder point"),
        ("Reorder point definition", "Average daily demand x lead time x 1.25 (set when the data was generated)"),
        ("Stockout day definition", "A day on which demand went unfilled (fulfilled < demand)"),
        ("Days-of-supply definition", "Final on-hand / average daily demand (on-hand only; inbound orders not counted)"),
        ("Turnover definition", "COGS (fulfilled units x unit cost) / average inventory value"),
        ("Dead stock definition", "Zero demand in the last 90 days of data"),
        ("Slow stock definition", "Average demand under 1 unit/day in the last 90 days, with stock still on hand"),
        ("Tools", "Python (pandas, sqlite3, openpyxl, matplotlib); SQL queries in sql/; this workbook"),
    ]
    ws.append(["Parameter", "Value / note"])
    for k, v in inputs:
        ws.append([k, v])
    style_header(ws, 1, 2)
    ws.column_dimensions["A"].width = 34
    ws.column_dimensions["B"].width = 110
    ws.freeze_panes = "A2"

    # --- Demand: monthly rollup by SKU ----------------------------------
    dem["month"] = dem["date"].dt.strftime("%Y-%m")
    pivot = (dem.pivot_table(index=["sku_id", "warehouse"],
                             columns="month", values="units_demanded",
                             aggfunc="sum", fill_value=0)
             .reset_index())
    pivot = pivot.merge(prod[["sku_id", "sku_name"]], on="sku_id")
    months = [c for c in pivot.columns if c.startswith("2026-")]
    cols = ["sku_id", "sku_name", "warehouse"] + months + []
    pivot["Total"] = pivot[months].sum(axis=1)
    pivot["Avg daily"] = (pivot["Total"] / 365).round(2)
    demand_sheet = pivot[["sku_id", "sku_name", "warehouse"] + months
                         + ["Total", "Avg daily"]]
    ws = wb.create_sheet("Demand")
    write_sheet(ws, demand_sheet,
                widths={"sku_id": 10, "sku_name": 34, "warehouse": 11,
                        "Total": 11, "Avg daily": 10})

    # --- Forecast --------------------------------------------------------
    fc_sheet = fc[["sku_id", "sku_name", "warehouse", "lead_time_days",
                   "on_hand", "ma_forecast_daily", "ses_forecast_daily",
                   "chosen_method", "chosen_forecast_daily", "ma_mape",
                   "ses_mape", "demand_std_daily", "safety_stock",
                   "forecast_during_lead_time", "recommended_order_qty",
                   "note"]]
    ws = wb.create_sheet("Forecast")
    write_sheet(ws, fc_sheet,
                formats={"lead_time_days": INT_FMT, "on_hand": INT_FMT,
                         "ma_forecast_daily": ONE_DEC_FMT,
                         "ses_forecast_daily": ONE_DEC_FMT,
                         "chosen_forecast_daily": ONE_DEC_FMT,
                         "ma_mape": PCT_FMT, "ses_mape": PCT_FMT,
                         "demand_std_daily": ONE_DEC_FMT,
                         "safety_stock": ONE_DEC_FMT,
                         "forecast_during_lead_time": ONE_DEC_FMT,
                         "recommended_order_qty": INT_FMT},
                widths={"sku_id": 10, "sku_name": 34, "warehouse": 11,
                        "chosen_method": 22, "note": 52})

    # --- Inventory Health -------------------------------------------------
    health = (prod[["sku_id", "sku_name", "warehouse", "unit_cost",
                    "lead_time_days", "reorder_point"]]
              .merge(snap[["sku_id", "on_hand", "on_hand_value"]], on="sku_id")
              .merge(turnover[["sku_id", "cogs", "avg_inventory_value",
                               "turnover"]], on="sku_id")
              .merge(dos[["sku_id", "avg_daily_demand", "days_of_supply"]],
                     on="sku_id")
              .merge(stockouts[["sku_id", "stockout_days"]], on="sku_id")
              .merge(breaches[["sku_id", "breach_days"]], on="sku_id")
              .merge(slow[["sku_id", "movement"]], on="sku_id", how="left"))
    health["movement"] = health["movement"].fillna("")
    health = health[["sku_id", "sku_name", "warehouse", "unit_cost",
                     "lead_time_days", "reorder_point", "on_hand",
                     "on_hand_value", "cogs", "avg_inventory_value",
                     "turnover", "avg_daily_demand", "days_of_supply",
                     "stockout_days", "breach_days", "movement"]]
    ws = wb.create_sheet("Inventory Health")
    write_sheet(ws, health,
                formats={"unit_cost": MONEY_FMT, "on_hand": INT_FMT,
                         "on_hand_value": MONEY_FMT, "cogs": MONEY_FMT,
                         "avg_inventory_value": MONEY_FMT,
                         "turnover": '0.00',
                         "avg_daily_demand": ONE_DEC_FMT,
                         "days_of_supply": ONE_DEC_FMT,
                         "stockout_days": INT_FMT, "breach_days": INT_FMT},
                widths={"sku_id": 10, "sku_name": 34, "warehouse": 11})
    # Flag stockouts red and thin cover amber on the Health sheet.
    n = len(health) + 1
    ws.conditional_formatting.add(f"N2:N{n}",
                                  CellIsRule(operator="greaterThan",
                                             formula=["0"], fill=RED_FILL))
    ws.conditional_formatting.add(f"M2:M{n}",
                                  CellIsRule(operator="lessThan",
                                             formula=["7"], fill=AMBER_FILL))

    # --- Recommendations: the memo's action table -------------------------
    # Only SKUs that need an action get a row. A SKU whose recommended
    # order is 0 and whose cover is adequate needs nothing, so it gets no
    # row (the memo names those three explicitly instead). Note: breach
    # days are NOT used as an action trigger — on-hand sits below the
    # reorder point for part of every normal replenishment cycle, so
    # breach days alone are not a problem signal; stockouts are.
    health_idx = health.set_index("sku_id")
    fc_idx = fc.set_index("sku_id")
    slow_idx = slow.set_index("sku_id") if len(slow) else None
    actions = []
    for sku in prod["sku_id"]:
        h = health_idx.loc[sku]
        f = fc_idx.loc[sku]
        name = h["sku_name"]
        if h["movement"] == "dead":
            actions.append(("Medium", "Do not reorder - review for clearance or return",
                            sku, name,
                            f"No demand in the last 90 days; {int(h['on_hand']):,} units "
                            f"still on hand (${h['on_hand_value']:,.2f}). Stop replenishment "
                            f"and review for clearance, bundling, or return to supplier."))
        elif h["movement"] == "slow":
            avg90 = float(slow_idx.loc[sku, "avg_daily_90d"])
            actions.append(("Low", "Hold - slow mover, do not top up",
                            sku, name,
                            f"Only {avg90:.2f} units/day in the last 90 days; "
                            f"{int(h['on_hand']):,} units on hand is already about "
                            f"{int(round(h['on_hand'] / avg90)) if avg90 > 0 else 0} days "
                            f"of cover. Do not reorder until demand picks up."))
        elif (f["recommended_order_qty"] > 0
              and (h["on_hand"] < h["reorder_point"]
                   or h["days_of_supply"] < h["lead_time_days"])):
            priority = ("High" if (h["on_hand"] <= 0
                                   or (h["stockout_days"] > 0
                                       and f["recommended_order_qty"] >= 50))
                        else "Medium")
            actions.append((priority, "Reorder", sku, name,
                            f"Order {int(f['recommended_order_qty']):,} units: "
                            f"{int(h['lead_time_days'])} days of forecast demand "
                            f"({f['forecast_during_lead_time']:,.0f}) + safety stock "
                            f"({f['safety_stock']:,.0f}) - on-hand ({int(h['on_hand']):,}). "
                            f"Current cover is {h['days_of_supply']:.1f} days."))
    priority_order = {"High": 0, "Medium": 1, "Low": 2}
    actions.sort(key=lambda a: priority_order[a[0]])
    rec = pd.DataFrame(actions, columns=["Priority", "Action", "SKU",
                                         "SKU name", "Detail"])
    ws = wb.create_sheet("Recommendations")
    write_sheet(ws, rec, widths={"Priority": 10, "Action": 40, "SKU": 10,
                                 "SKU name": 34, "Detail": 110})
    for r in range(2, len(rec) + 2):
        ws.cell(row=r, column=5).alignment = Alignment(wrap_text=True,
                                                       vertical="top")
    print(f"Workbook sheets: {wb.sheetnames}")
    print(f"Recommendation rows: {len(rec)} "
          f"(High: {(rec['Priority'] == 'High').sum()}, "
          f"Medium: {(rec['Priority'] == 'Medium').sum()}, "
          f"Low: {(rec['Priority'] == 'Low').sum()})")

    out_path = os.path.join(BASE, "inventory_model.xlsx")
    wb.save(out_path)
    print(f"Saved {out_path}")

    # Print the action table + headline numbers for the memo and README.
    print("\n--- ACTION TABLE (memo / README) ---")
    print(rec.to_string(index=False))
    acted = set(rec["SKU"])
    no_action = [s for s in prod["sku_id"] if s not in acted]
    print(f"\nNo action needed (cover already adequate): {no_action}")
    print("\n--- HEADLINE NUMBERS ---")
    print(f"Total demand: {int(demand_by['total_demand'].sum()):,} units")
    print(f"Total recommended order: {int(fc['recommended_order_qty'].sum()):,} units")
    print(f"Total on-hand value: ${snap['on_hand_value'].sum():,.2f}")
    print(f"Dead stock: {slow[slow['movement'] == 'dead']['sku_id'].tolist()} "
          f"(${slow[slow['movement'] == 'dead']['on_hand_value'].sum():,.2f})")
    print(f"Slow stock: {slow[slow['movement'] == 'slow']['sku_id'].tolist()}")
    top_stock = stockouts.iloc[0]
    print(f"Most stockout days: {top_stock['sku_id']} {top_stock['sku_name']} "
          f"({int(top_stock['stockout_days'])} days)")


if __name__ == "__main__":
    main()
