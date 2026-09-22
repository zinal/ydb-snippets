-- Список пользовательских таблиц с оценкой строк и размера
-- Usage: psql -f sample-data/list-tables.sql

SELECT
  n.nspname AS schema,
  c.relname AS table_name,
  c.reltuples::bigint AS est_rows,
  pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size,
  pg_size_pretty(pg_relation_size(c.oid)) AS table_size
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind IN ('r', 'p')
  AND n.nspname NOT IN ('pg_catalog', 'information_schema')
ORDER BY pg_total_relation_size(c.oid) DESC, n.nspname, c.relname;
