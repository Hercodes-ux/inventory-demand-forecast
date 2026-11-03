-- (a) Demand by SKU and warehouse: total and average daily demand.
-- One row per SKU (each SKU is stocked at a single warehouse).
SELECT
    p.sku_id,
    p.sku_name,
    p.warehouse,
    COUNT(*) AS days,
    SUM(d.units_demanded) AS total_demand,
    ROUND(AVG(d.units_demanded), 2) AS avg_daily_demand
FROM demand_daily d
JOIN products p
  ON p.sku_id = d.sku_id AND p.warehouse = d.warehouse
GROUP BY p.sku_id, p.sku_name, p.warehouse
ORDER BY total_demand DESC;
