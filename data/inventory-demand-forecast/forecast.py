"""Forecast demand per SKU and recommend order quantities.

Methods (per SKU, on its daily demand series):
  (a) 30-day moving-average forecast: mean of the last 30 training days.
  (b) Simple exponential smoothing (alpha = 0.3): level updated as
      level = alpha * actual + (1 - alpha) * level over training days.
  (c) Accuracy on a last-30-days holdout: MAPE = mean(|actual - forecast|
      / actual) over holdout days with actual > 0. The method with the
      lower MAPE is the chosen forecast for that SKU.
  (d) Recommended order quantity =
        chosen daily forecast x lead time + safety stock - on-hand,
      floored at 0. Safety stock = 1.65 x std(daily demand) x sqrt(lead
      time), i.e. a 95% service level under a normal-demand assumption.
      SKUs with zero demand in the last 90 days are flagged dead stock
      and get a recommended order of 0 regardless of the formula.

Outputs:
  outputs/forecast.csv       - one row per SKU
  outputs/forecast_daily.csv - daily actual / moving-average / SES series
                               for the 3 chart SKUs (audit trail)
  charts/forecast_<sku>.png  - demand vs forecast charts, 3 example SKUs

Run with:  python forecast.py
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import os
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
OUT = os.path.join(BASE, "outputs")
CHARTS = os.path.join(BASE, "charts")

ALPHA = 0.3
MA_WINDOW = 30
HOLDOUT_DAYS = 30
Z_95 = 1.65


def ses_forecast(series, alpha=ALPHA):
    """Final SES level after iterating over the series."""
    level = float(series.iloc[0])
    for x in series.iloc[1:]:
        level = alpha * float(x) + (1 - alpha) * level
    return level


def ses_fitted(series, alpha=ALPHA):
    """One-step-ahead SES fitted values, same length as the series."""
    fitted = []
    level = float(series.iloc[0])
    fitted.append(level)
    for x in series.iloc[1:]:
        level = alpha * float(x) + (1 - alpha) * level
        fitted.append(level)
    return np.array(fitted)


def mape(actual, forecast):
    """Mean absolute percentage error over days with actual > 0."""
    actual = np.asarray(actual, dtype=float)
    mask = actual > 0
    if mask.sum() == 0:
        return np.nan
    return float(np.mean(np.abs(actual[mask] - forecast) / actual[mask]) * 100)


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(CHARTS, exist_ok=True)
    dem = pd.read_csv(os.path.join(DATA, "demand_daily.csv"),
                      parse_dates=["date"])
    prod = pd.read_csv(os.path.join(DATA, "products.csv"))
    snap = pd.read_csv(os.path.join(DATA, "inventory_snapshot.csv"))
    last90 = dem[dem["date"] > dem["date"].max() - pd.Timedelta(days=90)]
    dead = set(last90.groupby("sku_id")["units_demanded"].sum().loc[
        lambda s: s == 0].index)

    rows = []
    series_by_sku = {}
    for _, p in prod.iterrows():
        sku = p["sku_id"]
        s = (dem[dem["sku_id"] == sku].sort_values("date")
             .reset_index(drop=True))
        series_by_sku[sku] = s
        train = s["units_demanded"].iloc[:-HOLDOUT_DAYS]
        holdout = s["units_demanded"].iloc[-HOLDOUT_DAYS:]
        ma_fc = float(train.tail(MA_WINDOW).mean())
        ses_fc = ses_forecast(train)
        ma_err = mape(holdout, ma_fc)
        ses_err = mape(holdout, ses_fc)
        if np.isnan(ma_err) and np.isnan(ses_err):
            chosen, chosen_fc = "moving_average", ma_fc
        elif np.isnan(ma_err):
            chosen, chosen_fc = "exponential_smoothing", ses_fc
        elif np.isnan(ses_err):
            chosen, chosen_fc = "moving_average", ma_fc
        else:
            chosen, chosen_fc = (
                ("moving_average", ma_fc) if ma_err <= ses_err
                else ("exponential_smoothing", ses_fc))
        lead = int(p["lead_time_days"])
        on_hand = int(snap.loc[snap["sku_id"] == sku, "on_hand"].iloc[0])
        std_daily = float(train.std(ddof=1))
        safety = Z_95 * std_daily * np.sqrt(lead)
        fc_during_lead = chosen_fc * lead
        if sku in dead:
            rec_qty, note = 0, "dead stock: no demand in last 90 days, do not reorder"
        else:
            rec_qty = max(0, int(round(fc_during_lead + safety - on_hand)))
            note = ""
        rows.append({
            "sku_id": sku,
            "sku_name": p["sku_name"],
            "warehouse": p["warehouse"],
            "lead_time_days": lead,
            "on_hand": on_hand,
            "ma_forecast_daily": round(ma_fc, 2),
            "ses_forecast_daily": round(ses_fc, 2),
            "chosen_method": chosen,
            "chosen_forecast_daily": round(chosen_fc, 2),
            "ma_mape": None if np.isnan(ma_err) else round(ma_err, 2),
            "ses_mape": None if np.isnan(ses_err) else round(ses_err, 2),
            "demand_std_daily": round(std_daily, 2),
            "safety_stock": round(safety, 1),
            "forecast_during_lead_time": round(fc_during_lead, 1),
            "recommended_order_qty": rec_qty,
            "note": note,
        })
    fc = pd.DataFrame(rows)
    fc.to_csv(os.path.join(OUT, "forecast.csv"), index=False)
    print(f"Wrote forecast.csv ({len(fc)} SKUs)")
    print(f"Total recommended order quantity: {fc['recommended_order_qty'].sum():,} units")
    print(f"SKUs with a recommended order: {(fc['recommended_order_qty'] > 0).sum()}")
    print(f"Chosen method counts:\n{fc['chosen_method'].value_counts().to_string()}")
    print(f"MAPE (chosen method) median: "
          f"{fc.apply(lambda r: r['ma_mape'] if r['chosen_method'] == 'moving_average' else r['ses_mape'], axis=1).median():.2f}%")

    # --- Charts: top seller, promo/stockout story, seasonal example ---
    # Top seller comes from the data; SKU-201 is the promotion case with
    # the most unfilled units (1,511) and a 21-day lead time; SKU-106 is
    # the seasonal summer SKU. Together they show steady, spiky, and
    # seasonal demand against the same two forecast methods.
    top_seller = dem.groupby("sku_id")["units_demanded"].sum().idxmax()
    chart_skus = []
    for sku in [top_seller, "SKU-201", "SKU-106"]:
        if sku not in chart_skus:
            chart_skus.append(sku)
    chart_skus = chart_skus[:3]

    daily_frames = []
    for sku in chart_skus:
        s = series_by_sku[sku].copy()
        s["ma30"] = s["units_demanded"].rolling(MA_WINDOW).mean()
        s["ses_fitted"] = ses_fitted(s["units_demanded"])
        s = s.iloc[-150:]  # last 150 days keep the chart readable
        daily_frames.append(s[["date", "sku_id", "units_demanded", "ma30",
                               "ses_fitted"]])
        name = prod.loc[prod["sku_id"] == sku, "sku_name"].iloc[0]
        fig, ax = plt.subplots(figsize=(12, 5))
        ax.plot(s["date"], s["units_demanded"], label="Actual demand",
                linewidth=1)
        ax.plot(s["date"], s["ma30"], label="30-day moving average",
                linewidth=1.5)
        ax.plot(s["date"], s["ses_fitted"],
                label="Exponential smoothing (alpha=0.3)", linewidth=1.5)
        ax.set_title(f"{sku} {name}: daily demand vs forecast (last 150 days)")
        ax.set_xlabel("Date")
        ax.set_ylabel("Units per day")
        ax.legend()
        ax.grid(True, alpha=0.3)
        fig.autofmt_xdate()
        fig.tight_layout()
        path = os.path.join(CHARTS, f"forecast_{sku}.png")
        fig.savefig(path, dpi=150)
        plt.close(fig)
        print(f"Chart: {path}")
    pd.concat(daily_frames).to_csv(
        os.path.join(OUT, "forecast_daily.csv"), index=False)


if __name__ == "__main__":
    main()
