-- data/schema.sql (SQLite) translated to Postgres.
-- fraud_labels.transaction_id stays TEXT, exactly as in the source; join with t.id::text.
CREATE TABLE data.users (
    id                          INTEGER PRIMARY KEY,
    birth_date                  DATE,
    gender                      TEXT CHECK (gender IN ('Male', 'Female')),
    address                     TEXT,
    latitude                    REAL,
    longitude                   REAL,
    per_capita_income_usd_cents INTEGER,
    yearly_income_usd_cents     INTEGER,
    total_debt_usd_cents        INTEGER,
    credit_score                INTEGER
);

CREATE TABLE data.mcc_codes (
    mcc         INTEGER PRIMARY KEY,
    description TEXT
);

CREATE TABLE data.merchants (
    id   INTEGER PRIMARY KEY,
    name TEXT,
    mcc  INTEGER REFERENCES data.mcc_codes (mcc)
);

CREATE TABLE data.merchant_locations (
    id          INTEGER PRIMARY KEY,
    merchant_id INTEGER REFERENCES data.merchants (id),
    city        TEXT,
    state       TEXT,
    zip         INTEGER
);

CREATE TABLE data.cards (
    id                     INTEGER PRIMARY KEY,
    user_id                INTEGER REFERENCES data.users (id),
    card_brand             TEXT CHECK (card_brand IN ('Amex', 'Discover', 'Mastercard', 'Visa')),
    card_type              TEXT CHECK (card_type IN ('Credit', 'Debit', 'Debit (Prepaid)')),
    expires                DATE,
    has_chip               BOOLEAN,
    credit_limit_usd_cents INTEGER,
    acct_open_date         DATE,
    year_pin_last_changed  INTEGER,
    card_on_dark_web       BOOLEAN
);

CREATE TABLE data.fraud_labels (
    transaction_id TEXT PRIMARY KEY,
    is_fraud       BOOLEAN
);

CREATE TABLE data.transactions (
    id                   INTEGER PRIMARY KEY,
    date                 TIMESTAMP,
    card_id              INTEGER REFERENCES data.cards (id),
    amount_usd_cents     INTEGER,
    transaction_type     TEXT CHECK (transaction_type IN
                             ('Chip Transaction', 'Online Transaction', 'Swipe Transaction')),
    merchant_id          INTEGER REFERENCES data.merchants (id),
    merchant_location_id INTEGER REFERENCES data.merchant_locations (id),
    errors               TEXT CHECK (errors IN
                             ('Bad CVV', 'Bad Card Number', 'Bad Expiration', 'Bad PIN',
                              'Bad Zipcode', 'Insufficient Balance', 'Technical Glitch'))
);

-- Indexes for the common joins and time filters the agent writes.
CREATE INDEX transactions_card_id_idx     ON data.transactions (card_id);
CREATE INDEX transactions_merchant_id_idx ON data.transactions (merchant_id);
CREATE INDEX transactions_date_idx        ON data.transactions (date);
-- Lets the documented fraud_labels.transaction_id = t.id::text join use an index.
CREATE INDEX transactions_id_text_idx     ON data.transactions ((id::text));
