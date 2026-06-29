-- Migration 003: Daily context cache (ephemeral, wiped at 23:59:59 ET each day)
--
-- Stores the assembled daily plan for a user keyed on (user_id, plan_date).
-- The agent reads this table live during every call instead of having the plan
-- baked into the system prompt at call-creation time.

CREATE TABLE IF NOT EXISTS daily_context (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  plan_date DATE NOT NULL,

  -- Raw fetched data (JSON blobs)
  calendar_events  JSONB NOT NULL DEFAULT '[]',
  weather          JSONB,
  commute          JSONB,

  -- LLM-generated summaries
  calendar_summary  TEXT NOT NULL DEFAULT '',
  weather_summary   TEXT NOT NULL DEFAULT '',
  commute_summary   TEXT NOT NULL DEFAULT '',
  workout_recommendation JSONB,
  leave_time        TIMESTAMP WITH TIME ZONE,
  carry_items       TEXT[] NOT NULL DEFAULT '{}',
  final_summary     TEXT NOT NULL DEFAULT '',

  -- Freshness tracking
  last_refreshed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  refresh_count     INTEGER NOT NULL DEFAULT 1,

  CONSTRAINT daily_context_user_date_unique UNIQUE (user_id, plan_date)
);

CREATE INDEX IF NOT EXISTS idx_daily_context_user_id   ON daily_context(user_id);
CREATE INDEX IF NOT EXISTS idx_daily_context_plan_date ON daily_context(plan_date);

ALTER TABLE daily_context ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own daily context"
  ON daily_context FOR SELECT
  USING (auth.uid() = user_id);

-- Cleanup function: delete all rows older than today (call at 23:59:59 ET via cron)
CREATE OR REPLACE FUNCTION wipe_stale_daily_context()
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
  deleted_count INTEGER;
BEGIN
  DELETE FROM daily_context
  WHERE plan_date < (NOW() AT TIME ZONE 'America/New_York')::DATE;

  GET DIAGNOSTICS deleted_count = ROW_COUNT;
  RETURN deleted_count;
END;
$$;
