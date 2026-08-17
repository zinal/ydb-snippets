-- Размеры объектов текущей БД
-- Usage: psql -f state/03-sizes.sql

\echo === top relations by total size ===
SELECT
  n.nspname AS schema,
  c.relname AS relation,
  c.relkind,
  pg_size_pretty(pg_total_relation_size(c.oid)) AS total,
  pg_size_pretty(pg_relation_size(c.oid)) AS main,
  pg_size_pretty(pg_indexes_size(c.oid)) AS indexes,
  pg_size_pretty(COALESCE(pg_total_relation_size(c.reltoastrelid), 0)) AS toast,
  c.reltuples::bigint AS est_rows
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind IN ('r', 'p', 'm', 'i')  -- table, partitioned, matview, index
  AND n.nspname NOT IN ('pg_catalog', 'information_schema')
ORDER BY pg_total_relation_size(c.oid) DESC
LIMIT 50;

\echo === tables only (heap + toast + indexes) ===
SELECT
  schemaname AS schema,
  relname AS table_name,
  pg_size_pretty(pg_total_relation_size(relid)) AS total,
  pg_size_pretty(pg_table_size(relid)) AS table_and_toast,
  pg_size_pretty(pg_indexes_size(relid)) AS indexes,
  n_live_tup AS live_est,
  n_dead_tup AS dead_est,
  last_vacuum,
  last_autovacuum,
  last_analyze,
  last_autoanalyze
FROM pg_stat_user_tables
ORDER BY pg_total_relation_size(relid) DESC
LIMIT 50;
