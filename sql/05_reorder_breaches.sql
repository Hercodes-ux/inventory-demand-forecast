-- (e) Reorder-point breaches by SKU: days where end-of-day on-hand
-- fell below the SKU's reorder point (an order should have been placed
-- or was already in transit). Frequent breaches flag a reorder point or
-- lead time that needs review.
SELECT
    p.sku_id,
    p.sku_name,
    p.warehouse,
    p.reorder_point,
    SUM(CASE WHEN i.on_hand_end < p.reorder_point THEN 1 ELSE 0 END) AS breach_days
FROM products p
LEFT JOIN inventory_daily i
  ON i.sku_id = p.sku_id AND i.warehouse = p.warehouse
GROUP BY p.sku_id, p.sku_name, p.warehouse, p.reorder_point
ORDER BY breach_days DESC, p.sku_id;
