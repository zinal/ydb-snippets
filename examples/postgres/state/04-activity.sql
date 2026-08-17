-- Активность: соединения, текущие запросы, долгие транзакции
-- Usage: psql -f state/04-activity.sql

\echo === connection summary ===
SELECT
  state,
  count(*) AS sessions,
  count(*) FILTER (WHERE wait_event_type IS NOT NULL) AS waiting
FROM pg_stat_activity
WHERE backend_type = 'client backend'
GROUP BY state
ORDER BY sessions DESC;

\echo === by database / user / application ===
SELECT
  datname,
  usename,
  application_name,
  client_addr,
  state,
  count(*) AS sessions
FROM pg_stat_activity
WHERE backend_type = 'client backend'
GROUP BY 1, 2, 3, 4, 5
ORDER BY sessions DESC, datname, usename;

\echo === running / idle-in-transaction (exclude self) ===
SELECT
  pid,
  datname,
  usename,
  application_name,
  client_addr,
  state,
  wait_event_type,
  wait_event,
  now() - xact_start AS xact_age,
  now() - query_start AS query_age,
  left(query, 200) AS query
FROM pg_stat_activity
WHERE backend_type = 'client backend'
  AND pid <> pg_backend_pid()
  AND state IS DISTINCT FROM 'idle'
ORDER BY xact_start NULLS LAST, query_start NULLS LAST
LIMIT 40;

\echo === longest transactions ===
SELECT
  pid,
  datname,
  usename,
  state,
  now() - xact_start AS xact_age,
  left(query, 160) AS query
FROM pg_stat_activity
WHERE xact_start IS NOT NULL
  AND pid <> pg_backend_pid()
ORDER BY xact_start
LIMIT 20;
