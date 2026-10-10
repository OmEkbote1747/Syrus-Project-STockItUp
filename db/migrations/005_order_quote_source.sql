-- Preserve the market-data source used when the trader reviewed a draft.
ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS quote_provider VARCHAR(32),
    ADD COLUMN IF NOT EXISTS quote_mode VARCHAR(32);
