-- Reclaim — schema
-- Apply via Supabase MCP or psql $DATABASE_URL -f backend/db/schema.sql
-- Source of truth: docs/reclaim-build-plan.md §2

CREATE TABLE IF NOT EXISTS merchants (
  merchant_id TEXT PRIMARY KEY,
  max_retries INT NOT NULL DEFAULT 3,
  contact_budget_per_day INT NOT NULL DEFAULT 2
);

CREATE TABLE IF NOT EXISTS customers (
  customer_id TEXT PRIMARY KEY,
  recovery_propensity NUMERIC NOT NULL,
  payment_method_preference TEXT,
  historical_success_rate NUMERIC,
  customer_value NUMERIC NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
  order_id TEXT PRIMARY KEY,
  merchant_id TEXT REFERENCES merchants(merchant_id),
  customer_id TEXT REFERENCES customers(customer_id),
  amount NUMERIC NOT NULL,
  currency TEXT NOT NULL DEFAULT 'INR',
  status TEXT NOT NULL DEFAULT 'pending',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_merchant ON orders(merchant_id);
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at DESC);

CREATE TABLE IF NOT EXISTS payment_attempts (
  payment_id TEXT PRIMARY KEY,
  order_id TEXT REFERENCES orders(order_id),
  attempt_number INT NOT NULL,
  method TEXT NOT NULL,
  status TEXT NOT NULL,
  error_code TEXT,
  error_description TEXT,
  error_reason TEXT,
  error_source TEXT,
  error_step TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_attempts_order ON payment_attempts(order_id);
CREATE INDEX IF NOT EXISTS idx_attempts_status ON payment_attempts(status);

CREATE TABLE IF NOT EXISTS webhook_events (
  event_id TEXT PRIMARY KEY,
  event_type TEXT NOT NULL,
  payload JSONB NOT NULL,
  processed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_webhook_type ON webhook_events(event_type);
CREATE INDEX IF NOT EXISTS idx_webhook_processed ON webhook_events(processed_at);

CREATE TABLE IF NOT EXISTS recovery_actions (
  action_id SERIAL PRIMARY KEY,
  order_id TEXT REFERENCES orders(order_id),
  action_type TEXT NOT NULL,
  expected_value NUMERIC NOT NULL,
  status TEXT NOT NULL DEFAULT 'scheduled',
  scheduled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  executed_at TIMESTAMPTZ,
  cancelled_at TIMESTAMPTZ,
  reason TEXT,
  recommended_method TEXT,
  explanation TEXT,
  explanation_model TEXT
);

ALTER TABLE recovery_actions
  ADD COLUMN IF NOT EXISTS recommended_method TEXT;
ALTER TABLE recovery_actions
  ADD COLUMN IF NOT EXISTS explanation TEXT;
ALTER TABLE recovery_actions
  ADD COLUMN IF NOT EXISTS explanation_model TEXT;

CREATE INDEX IF NOT EXISTS idx_recovery_order ON recovery_actions(order_id);
CREATE INDEX IF NOT EXISTS idx_recovery_status ON recovery_actions(status);

-- RLS is enabled as a placeholder for future multi-tenant isolation.
-- Current backend connects as DB owner (bypasses RLS).
-- Policies will be added when multi-tenant auth is implemented.
ALTER TABLE merchants         ENABLE ROW LEVEL SECURITY;
ALTER TABLE customers         ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders            ENABLE ROW LEVEL SECURITY;
ALTER TABLE payment_attempts  ENABLE ROW LEVEL SECURITY;
ALTER TABLE webhook_events    ENABLE ROW LEVEL SECURITY;
ALTER TABLE recovery_actions  ENABLE ROW LEVEL SECURITY;

-- No policies yet — RLS is enabled but permissive until multi-tenant auth.
-- Future: CREATE POLICY ... USING (merchant_id = current_setting('app.current_merchant_id'));
