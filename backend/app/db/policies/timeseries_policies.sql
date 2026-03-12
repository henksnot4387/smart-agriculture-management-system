CREATE EXTENSION IF NOT EXISTS timescaledb;

-- 15-minute downsampling tier (for >24h and <=30d queries)
CREATE MATERIALIZED VIEW IF NOT EXISTS sensor_samples_15m
WITH (
  timescaledb.continuous,
  timescaledb.materialized_only = true
) AS
SELECT
  time_bucket(INTERVAL '15 minutes', recorded_at) AS bucket_start,
  greenhouse_zone,
  COALESCE(extras->>'provider', '') AS provider,
  COALESCE(extras->>'source', '') AS source,
  sample.metric,
  AVG(sample.value::double precision) AS avg_value,
  MIN(sample.value::double precision) AS min_value,
  MAX(sample.value::double precision) AS max_value,
  COUNT(*)::bigint AS sample_count
FROM sensor_data
CROSS JOIN LATERAL (
  VALUES
    ('temperature', sensor_data.temperature),
    ('humidity', sensor_data.humidity),
    ('ec', sensor_data.ec),
    ('ph', sensor_data.ph)
) AS sample(metric, value)
WHERE sample.value IS NOT NULL
GROUP BY 1, 2, 3, 4, 5
WITH NO DATA;

-- Daily downsampling tier (for >30d queries)
CREATE MATERIALIZED VIEW IF NOT EXISTS sensor_samples_1d
WITH (
  timescaledb.continuous,
  timescaledb.materialized_only = true
) AS
SELECT
  time_bucket(INTERVAL '1 day', recorded_at) AS bucket_start,
  greenhouse_zone,
  COALESCE(extras->>'provider', '') AS provider,
  COALESCE(extras->>'source', '') AS source,
  sample.metric,
  AVG(sample.value::double precision) AS avg_value,
  MIN(sample.value::double precision) AS min_value,
  MAX(sample.value::double precision) AS max_value,
  COUNT(*)::bigint AS sample_count
FROM sensor_data
CROSS JOIN LATERAL (
  VALUES
    ('temperature', sensor_data.temperature),
    ('humidity', sensor_data.humidity),
    ('ec', sensor_data.ec),
    ('ph', sensor_data.ph)
) AS sample(metric, value)
WHERE sample.value IS NOT NULL
GROUP BY 1, 2, 3, 4, 5
WITH NO DATA;

CREATE INDEX IF NOT EXISTS sensor_samples_15m_query_idx
ON sensor_samples_15m (bucket_start DESC, metric, greenhouse_zone, provider, source);

CREATE INDEX IF NOT EXISTS sensor_samples_1d_query_idx
ON sensor_samples_1d (bucket_start DESC, metric, greenhouse_zone, provider, source);

SELECT add_continuous_aggregate_policy(
  'sensor_samples_15m',
  start_offset => INTERVAL '32 days',
  end_offset => INTERVAL '5 minutes',
  schedule_interval => INTERVAL '15 minutes',
  if_not_exists => TRUE
);

SELECT add_continuous_aggregate_policy(
  'sensor_samples_1d',
  start_offset => INTERVAL '400 days',
  end_offset => INTERVAL '1 day',
  schedule_interval => INTERVAL '1 day',
  if_not_exists => TRUE
);

SELECT add_retention_policy(
  'sensor_data',
  drop_after => INTERVAL '45 days',
  if_not_exists => TRUE
);

SELECT add_retention_policy(
  'sensor_samples_15m',
  drop_after => INTERVAL '400 days',
  if_not_exists => TRUE
);

DO $$
DECLARE
  min_ts timestamptz;
BEGIN
  SELECT MIN(recorded_at) INTO min_ts FROM sensor_data;
  IF min_ts IS NULL THEN
    RETURN;
  END IF;

  CALL refresh_continuous_aggregate('sensor_samples_15m', min_ts, NOW() - INTERVAL '5 minutes');
  CALL refresh_continuous_aggregate('sensor_samples_1d', min_ts, NOW() - INTERVAL '1 day');
END $$;
