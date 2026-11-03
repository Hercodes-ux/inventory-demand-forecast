-- (f) Slow-moving and dead stock: demand in the last 90 days of data.
-- dead = zero demand in the last 90 days (nothing sold at all).
-- slow = average demand under 1 unit/day in the last 90 days.
SELECT
    p.sku_id,
    p.sku_name,
    p.warehouse,
    s.on_hand AS on_hand,
    s.on_hand_value AS on_hand_value,
    last90.demand_90d,
    ROUND(last90.avg_90d, 2) AS avg_daily_90d,
    CASE
        WHEN last90.demand_90d = 0 THEN 'dead'
        WHEN last90.avg_90d < 1 THEN 'slow'
    END AS movement
FROM products p
JOIN inventory_snapshot s
  ON s.sku_id = p.sku_id AND s.warehouse = p.warehouse
JOIN (
    SELECT
        sku_id,
        SUM(units_demanded) AS demand_90d,
        AVG(units_demanded) AS avg_90d
    FROM demand_daily
    WHERE date > date((SELECT MAX(date) FROM demand_daily), '-90 days')
    GROUP BY sku_id
) last90
  ON last90.sku_id = p.sku_id
WHERE last90.demand_90d = 0 OR last90.avg_90d < 1
ORDER BY last90.demand_90d ASC;
