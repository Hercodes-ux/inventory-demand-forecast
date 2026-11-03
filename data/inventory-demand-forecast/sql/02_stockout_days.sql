-- (b) Stockout days by SKU: days where demand went unfilled, i.e. the
-- day's demand exceeded the stock available that day (fulfilled < demand).
-- This is the same event as "end-of-day on-hand hit zero while demand was
-- present", and it deliberately excludes zero-stock days with zero demand
-- (for example a discontinued SKU sitting at zero after demand stopped).
-- LEFT JOIN so SKUs with zero stockout days still appear.
SELECT
    p.sku_id,
    p.sku_name,
    p.warehouse,
    SUM(CASE WHEN i.fulfilled < i.demand THEN 1 ELSE 0 END) AS stockout_days
FROM products p
LEFT JOIN inventory_daily i
  ON i.sku_id = p.sku_id AND i.warehouse = p.warehouse
GROUP BY p.sku_id, p.sku_name, p.warehouse
ORDER BY stockout_days DESC, p.sku_id;
