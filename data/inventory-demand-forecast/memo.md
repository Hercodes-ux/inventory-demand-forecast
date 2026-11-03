# Recommendations memo: inventory and demand forecast

**Operation covered:** 20 SKUs across 3 warehouses (Cleveland, Columbus, Chicago),
12 months of daily demand, 2026-01-01 to 2026-12-31.
**Basis:** every number below is computed by the SQL queries in `sql/` and by
`forecast.py` from the same data — nothing here is typed in by hand. The
matching detail lives in `inventory_model.xlsx` (Forecast and Inventory Health
sheets) and in `outputs/`.

## What the data shows

**Scale and service.** Total demand was 218,146 units. 215,780 units were
fulfilled and 2,366 went unfilled, a 98.92% fill rate. 8 of the 20 SKUs stocked
out at least once. The service problem is concentrated, not general — four
SKUs account for nearly all of the unfilled units.

**The worst stockout is a lead-time story.** SKU-201 Wireless Mouse stocked
out on 20 days with 1,511 unfilled units. It ran a 3-week promotion in late
July that multiplied demand by 2.2, against a 21-day supplier lead time — the
longest in the operation. By the time replenishment could arrive, the spike
was over and the sales were already lost. For the next promotion, the order
has to be placed before the promotion starts, not during it.

**The second-worst stockout is a discontinued line.** SKU-203 Bluetooth
Speaker Mini stocked out on 22 days with 372 unfilled units — all between
February 1 and September 27, before demand stopped on September 28. Its
reorder point was set from a full-year average that understated its
selling-season demand, so it ran lean while it was still selling. It now
holds 510 dead units worth $11,724.90 (see below).

**Seasonal peaks also broke stock.** SKU-106 Yoga Mat (summer peak) stocked
out 14 days with 357 unfilled units, and SKU-105 Electric Kettle 1.7L (winter
peak) stocked out 9 days with 115 unfilled units — and ends the year at zero
on hand, in the middle of its peak season. Seasonal SKUs need their reorder
points set from peak-season demand, not annual averages.

**Cover is thin at year end.** Four SKUs end the year under 4 days of supply
on hand: SKU-105 at 0.0 days, SKU-303 Desk Organizer Tray at 1.7 days,
SKU-205 Resistance Band Set at 3.4 days, and SKU-102 Stainless Steel Water
Bottle at 3.5 days. The recommended orders below total 1,853 units across 16
SKUs and close exactly this gap: forecast demand during each SKU's lead
time, plus safety stock at a 95% service level, minus what is already on hand.

**Dead and slow stock.** SKU-203 is dead: zero demand in the last 90 days,
510 units ($11,724.90) still on hand. Stop replenishing it and review
clearance, bundling, or return to supplier. SKU-308 Specialty Label Roll is
slow: 0.42 units/day in the last 90 days with 8 units on hand — hold it, do
not top it up. Total on-hand value across the operation is $69,692.48, so the
dead SKU alone is about 17% of the value sitting in stock.

**Forecast accuracy is honest, not flattering.** Median chosen-method MAPE
on the last-30-days holdout is 22.16%. Steady high-volume sellers forecast
well — SKU-201 at 7.67% and SKU-202 USB-C Charging Cable at 8.69%, both with
exponential smoothing. Small, sporadic sellers do not: SKU-308 at 53.12% and
SKU-304 Whiteboard Marker Set at 41.44%, because percentage errors blow up
when daily counts are tiny. Moving average was the better method for 11
SKUs, exponential smoothing for 9 — neither wins everywhere, which is why
the forecast is chosen per SKU. The safety stock is what absorbs this error;
it is not a reason to skip ordering.

**Turnover.** The fastest-moving stock turns about 45 times a year
(SKU-102 at 45.30x, SKU-301 Ballpoint Pen Box at 44.90x, SKU-202 at 44.89x);
the slowest is SKU-308 at 23.32x. These are high because the operation holds
roughly one to two weeks of stock and replenishes frequently — the number to
watch is the direction, not an external benchmark.

**No action needed.** SKU-101 Ceramic Mug, SKU-301 Ballpoint Pen Box, and
SKU-307 Packing Tape already hold enough to cover forecast demand during
their lead times plus safety stock. Their recommended order is zero.

## Action table

| Priority | Action | SKU | Detail |
|---|---|---|---|
| High | Reorder | SKU-105 Electric Kettle 1.7L | Order 169 units: 7 days of forecast demand (141) + safety stock (28) - on-hand (0). Current cover is 0.0 days. |
| High | Reorder | SKU-106 Yoga Mat | Order 81 units: 10 days of forecast demand (223) + safety stock (66) - on-hand (208). Current cover is 6.7 days. |
| High | Reorder | SKU-201 Wireless Mouse | Order 724 units: 21 days of forecast demand (1,329) + safety stock (150) - on-hand (755). Current cover is 11.8 days. |
| High | Reorder | SKU-303 Desk Organizer Tray | Order 87 units: 7 days of forecast demand (89) + safety stock (22) - on-hand (23). Current cover is 1.7 days. |
| Medium | Reorder | SKU-102 Stainless Steel Water Bottle 750ml | Order 133 units: 5 days of forecast demand (277) + safety stock (37) - on-hand (181). Current cover is 3.5 days. |
| Medium | Reorder | SKU-103 Cotton Bath Towel Set | Order 92 units: 10 days of forecast demand (236) + safety stock (27) - on-hand (171). Current cover is 7.2 days. |
| Medium | Reorder | SKU-104 LED Desk Lamp | Order 107 units: 14 days of forecast demand (249) + safety stock (29) - on-hand (170). Current cover is 9.3 days. |
| Medium | Reorder | SKU-202 USB-C Charging Cable 6ft | Order 21 units: 5 days of forecast demand (333) + safety stock (30) - on-hand (341). Current cover is 5.2 days. |
| Medium | Do not reorder - review for clearance or return | SKU-203 Bluetooth Speaker Mini | No demand in the last 90 days; 510 units still on hand ($11,724.90). Stop replenishment and review for clearance, bundling, or return to supplier. |
| Medium | Reorder | SKU-204 Laptop Stand Adjustable | Order 24 units: 10 days of forecast demand (137) + safety stock (18) - on-hand (131). Current cover is 10.0 days. |
| Medium | Reorder | SKU-205 Resistance Band Set | Order 103 units: 7 days of forecast demand (153) + safety stock (25) - on-hand (75). Current cover is 3.4 days. |
| Medium | Reorder | SKU-206 Handheld Vacuum | Order 127 units: 21 days of forecast demand (197) + safety stock (23) - on-hand (93). Current cover is 9.8 days. |
| Medium | Reorder | SKU-302 A4 Notebook Pack (3) | Order 4 units: 5 days of forecast demand (165) + safety stock (34) - on-hand (195). Current cover is 6.2 days. |
| Medium | Reorder | SKU-304 Whiteboard Marker Set | Order 67 units: 10 days of forecast demand (92) + safety stock (21) - on-hand (46). Current cover is 4.6 days. |
| Medium | Reorder | SKU-305 Cardboard Mailer Box S | Order 85 units: 5 days of forecast demand (294) + safety stock (48) - on-hand (258). Current cover is 4.6 days. |
| Medium | Reorder | SKU-306 Bubble Wrap Roll | Order 26 units: 7 days of forecast demand (178) + safety stock (33) - on-hand (184). Current cover is 7.3 days. |
| Low | Hold - slow mover, do not top up | SKU-308 Specialty Label Roll | Only 0.42 units/day in the last 90 days; 8 units on hand is already about 19 days of cover. Do not reorder until demand picks up. |

## Limitations

- **Synthetic data.** The dataset is simulated (seeded, reproducible). The
  analysis methods are the demonstration, not real company data, and the
  findings describe this simulated operation only.
- **No enterprise system.** Nothing here uses or claims hands-on experience
  with SAP, ERP, or any warehouse management system. The analysis is SQL,
  Python, and Excel on flat files.
- **A forecast is a planning aid, not a guarantee.** Holdout MAPE runs from
  7.67% to 53.12% depending on the SKU. Recommended orders pair the forecast
  with safety stock for exactly that reason, and they should be re-run as
  new demand arrives.
- **Fixed lead times, lost sales, no transfers.** Lead times are treated as
  fixed (supplier variability is not modeled), unfilled demand is treated as
  lost rather than backordered, and each SKU sits in one warehouse (no
  inter-warehouse transfers are modeled).
