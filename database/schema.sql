CREATE TABLE IF NOT EXISTS customers (
  id VARCHAR(36) PRIMARY KEY,
  name VARCHAR(160) NOT NULL,
  phone_number VARCHAR(24) NOT NULL,
  company_name VARCHAR(200),
  purpose VARCHAR(240),
  product VARCHAR(240),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_customers_phone_number ON customers(phone_number);

CREATE TABLE IF NOT EXISTS call_sessions (
  id VARCHAR(36) PRIMARY KEY,
  customer_id VARCHAR(36) NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
  provider_call_id VARCHAR(120),
  phone_number VARCHAR(24) NOT NULL,
  direction VARCHAR(20) NOT NULL DEFAULT 'outbound',
  status VARCHAR(40) NOT NULL DEFAULT 'created',
  outcome VARCHAR(80),
  lead_status VARCHAR(80),
  follow_up_required BOOLEAN NOT NULL DEFAULT FALSE,
  started_at TIMESTAMPTZ,
  ended_at TIMESTAMPTZ,
  duration_seconds INTEGER NOT NULL DEFAULT 0,
  agent_state JSONB NOT NULL DEFAULT '{}'::jsonb,
  structured_summary JSONB,
  summary_text TEXT,
  error_code VARCHAR(80),
  error_message TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_call_sessions_customer_id ON call_sessions(customer_id);
CREATE INDEX IF NOT EXISTS ix_call_sessions_status ON call_sessions(status);
CREATE INDEX IF NOT EXISTS ix_call_sessions_lead_status ON call_sessions(lead_status);
CREATE INDEX IF NOT EXISTS ix_call_sessions_follow_up ON call_sessions(follow_up_required);

CREATE TABLE IF NOT EXISTS conversation_turns (
  id VARCHAR(36) PRIMARY KEY,
  call_id VARCHAR(36) NOT NULL REFERENCES call_sessions(id) ON DELETE CASCADE,
  speaker VARCHAR(20) NOT NULL CHECK (speaker IN ('ai','customer','system')),
  message TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_conversation_turns_call_id ON conversation_turns(call_id);
CREATE INDEX IF NOT EXISTS ix_conversation_turns_created_at ON conversation_turns(created_at);

CREATE TABLE IF NOT EXISTS call_events (
  id VARCHAR(36) PRIMARY KEY,
  call_id VARCHAR(36) NOT NULL REFERENCES call_sessions(id) ON DELETE CASCADE,
  event_type VARCHAR(80) NOT NULL,
  details JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_call_events_call_id ON call_events(call_id);
