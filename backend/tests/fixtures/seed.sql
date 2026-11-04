-- 40 transactions with a known fraud pattern (fraud only at the Italian location):
--   ids  1-10  Rome, Italy   Chip    $100  labelled, 1-8 fraud
--   ids 11-30  Houston, TX   Swipe   $25   11-25 labelled (not fraud), 26-30 unlabelled
--   ids 31-40  ONLINE        Online  $50   31-35 labelled (not fraud), 36-40 unlabelled
-- => 40 transactions, 30 labelled, 8 fraud. Rule "Italy" matches 10, fraud rate 0.8.
INSERT INTO data.mcc_codes (mcc, description) VALUES
    (5311, 'Department Stores'),
    (5411, 'Grocery Stores, Supermarkets');

INSERT INTO data.merchants (id, name, mcc) VALUES
    (1, 'Merchant 1', 5311),
    (2, 'Merchant 2', 5411);

INSERT INTO data.merchant_locations (id, merchant_id, city, state, zip) VALUES
    (1, 1, 'Rome', 'Italy', NULL),
    (2, 2, 'Houston', 'TX', 77001),
    (3, 2, 'ONLINE', '', NULL);

INSERT INTO data.users (id, birth_date, gender, address, latitude, longitude,
                        per_capita_income_usd_cents, yearly_income_usd_cents,
                        total_debt_usd_cents, credit_score) VALUES
    (1, '1980-01-01', 'Female', '1 Main St', 29.7, -95.3, 3000000, 6000000, 1000000, 720),
    (2, '1990-06-15', 'Male', '2 Oak Ave', 40.7, -74.0, 2500000, 5000000, 2000000, 650);

INSERT INTO data.cards (id, user_id, card_brand, card_type, expires, has_chip,
                        credit_limit_usd_cents, acct_open_date, year_pin_last_changed,
                        card_on_dark_web) VALUES
    (10, 1, 'Visa', 'Credit', '2024-01-01', TRUE, 1000000, '2010-01-01', 2015, FALSE),
    (11, 2, 'Mastercard', 'Debit', '2025-01-01', TRUE, 500000, '2012-01-01', 2016, FALSE);

INSERT INTO data.transactions (id, date, card_id, amount_usd_cents, transaction_type,
                               merchant_id, merchant_location_id, errors)
SELECT id, TIMESTAMP '2019-03-01 12:00' + id * INTERVAL '1 day', 10, 10000,
       'Chip Transaction', 1, 1, NULL
FROM generate_series(1, 10) AS id
UNION ALL
SELECT id, TIMESTAMP '2019-03-01 12:00' + id * INTERVAL '1 day', 11, 2500,
       'Swipe Transaction', 2, 2, NULL
FROM generate_series(11, 30) AS id
UNION ALL
SELECT id, TIMESTAMP '2019-03-01 12:00' + id * INTERVAL '1 day', 11, 5000,
       'Online Transaction', 2, 3, NULL
FROM generate_series(31, 40) AS id;

INSERT INTO data.fraud_labels (transaction_id, is_fraud)
SELECT id::text, id <= 8
FROM generate_series(1, 25) AS id
UNION ALL
SELECT id::text, FALSE
FROM generate_series(31, 35) AS id;
