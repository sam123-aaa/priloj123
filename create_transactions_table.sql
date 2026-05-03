CREATE TABLE IF NOT EXISTS transactions (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NULL,
    role_code TEXT NULL,
    action TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    auth_user_id UUID NULL
);

CREATE INDEX IF NOT EXISTS idx_transactions_created_at
    ON transactions (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_transactions_user_id
    ON transactions (user_id);
