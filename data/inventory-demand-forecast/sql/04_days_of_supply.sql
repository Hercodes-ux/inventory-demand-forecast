-- (d) Days-of-supply by SKU: final on-hand / average daily demand.
-- Days-of-supply answers "how many days until this SKU runs out at the
-- current demand rate, with no new orders arriving?"
SELECT
    p.sku_id,
    p.sku_name,
    p.warehouse,
    s.on_hand AS on_hand,
    ROUND(AVG(d.units_demanded), 2) AS avg_daily_demand,
    ROUND(s.on_hand / NULLIF(AVG(d.units_demanded), 0), 1) AS days_of_supply
FROM products p
JOIN inventory_snapshot s
  ON s.sku_id = p.sku_id AND s.warehouse = p.warehouse
JOIN demand_daily d
  ON d.sku_id = p.sku_id AND d.warehouse = p.warehouse
GROUP BY p.sku_id, p.sku_name, p.warehouse, s.on_hand
ORDER BY days_of_supply ASC;
