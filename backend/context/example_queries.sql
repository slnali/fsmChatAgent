-- Layer 1: canonical queries. Reuse these patterns.

-- Fraud rate by transaction type (note the id::text join and labelled-only denominator).
SELECT t.transaction_type,
       COUNT(*)                     AS labelled,
       SUM(fl.is_fraud::int)        AS fraud,
       ROUND(AVG(fl.is_fraud::int) * 100, 3) AS fraud_rate_pct
FROM data.transactions t
JOIN data.fraud_labels fl ON fl.transaction_id = t.id::text
GROUP BY t.transaction_type
ORDER BY fraud_rate_pct DESC;

-- Monthly fraud trend.
SELECT date_trunc('month', t.date)::date AS month,
       SUM(fl.is_fraud::int)              AS fraud,
       ROUND(AVG(fl.is_fraud::int) * 100, 3) AS fraud_rate_pct
FROM data.transactions t
JOIN data.fraud_labels fl ON fl.transaction_id = t.id::text
GROUP BY 1
ORDER BY 1;

-- Top merchant categories by fraud count, with dollars.
SELECT mc.description            AS merchant_category,
       SUM(fl.is_fraud::int)     AS fraud,
       ROUND(AVG(fl.is_fraud::int) * 100, 3) AS fraud_rate_pct,
       ROUND(SUM(t.amount_usd_cents) FILTER (WHERE fl.is_fraud) / 100.0, 2) AS fraud_usd
FROM data.transactions t
JOIN data.fraud_labels fl ON fl.transaction_id = t.id::text
JOIN data.merchants m      ON m.id = t.merchant_id
JOIN data.mcc_codes mc     ON mc.mcc = m.mcc
GROUP BY mc.description
ORDER BY fraud DESC
LIMIT 10;

-- Validate a hypothesis: how a candidate rule segment compares with everything else.
SELECT (t.amount_usd_cents > 50000 AND t.transaction_type = 'Online Transaction') AS in_segment,
       COUNT(*)                 AS labelled,
       SUM(fl.is_fraud::int)    AS fraud,
       ROUND(AVG(fl.is_fraud::int) * 100, 3) AS fraud_rate_pct
FROM data.transactions t
JOIN data.fraud_labels fl ON fl.transaction_id = t.id::text
GROUP BY 1;

-- A rule WHERE clause can only reference data.transactions as t; use subqueries for other tables.
-- t.transaction_type = 'Online Transaction'
--   AND t.card_id IN (SELECT id FROM data.cards WHERE card_on_dark_web)
