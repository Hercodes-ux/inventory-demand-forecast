-- (c) Inventory turnover by SKU: COGS / average inventory value.
-- COGS = units actually fulfilled x unit cost over the year.
-- Average inventory value = average end-of-day on-hand x unit cost.
SELECT
    p.sku_id,
    p.sku_name,
    p.warehouse,
    ROUND(SUM(i.fulfilled * p.unit_cost), 2) AS cogs,
    ROUND(AVG(i.on_hand_end) * p.unit_cost, 2) AS avg_inventory_value,
    ROUND(SUM(i.fulfilled * p.unit_cost)
          / NULLIF(AVG(i.on_hand_end) * p.unit_cost, 0), 2) AS turnover
FROM products p
JOIN inventory_daily i
  ON i.sku_id = p.sku_id AND i.warehouse = p.warehouse
GROUP BY p.sku_id, p.sku_name, p.warehouse
ORDER BY turnover DESC;
