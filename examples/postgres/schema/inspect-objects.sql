-- Обзор объектов схемы (без pg_dump)
-- Usage: psql -f schema/inspect-objects.sql

\echo === tables / partitioned tables / foreign tables ===
SELECT
  n.nspname AS schema,
  c.relname AS name,
  CASE c.relkind
    WHEN 'r' THEN 'table'
    WHEN 'p' THEN 'partitioned table'
    WHEN 'f' THEN 'foreign table'
    ELSE c.relkind::text
  END AS kind,
  pg_get_userbyid(c.relowner) AS owner,
  c.reltuples::bigint AS est_rows
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind IN ('r', 'p', 'f')
  AND n.nspname NOT IN ('pg_catalog', 'information_schema')
ORDER BY 1, 2;

\echo === views / materialized views ===
SELECT
  n.nspname AS schema,
  c.relname AS name,
  CASE c.relkind WHEN 'v' THEN 'view' WHEN 'm' THEN 'matview' END AS kind
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind IN ('v', 'm')
  AND n.nspname NOT IN ('pg_catalog', 'information_schema')
ORDER BY 1, 2;

\echo === indexes ===
SELECT
  schemaname AS schema,
  tablename AS table_name,
  indexname AS index_name,
  indexdef
FROM pg_indexes
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY 1, 2, 3;

\echo === constraints ===
SELECT
  n.nspname AS schema,
  t.relname AS table_name,
  c.conname AS constraint_name,
  CASE c.contype
    WHEN 'p' THEN 'primary'
    WHEN 'u' THEN 'unique'
    WHEN 'f' THEN 'foreign'
    WHEN 'c' THEN 'check'
    WHEN 'x' THEN 'exclude'
    ELSE c.contype::text
  END AS type,
  pg_get_constraintdef(c.oid, true) AS definition
FROM pg_constraint c
JOIN pg_class t ON t.oid = c.conrelid
JOIN pg_namespace n ON n.oid = t.relnamespace
WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
ORDER BY 1, 2, 4, 3;

\echo === functions / procedures (signatures) ===
SELECT
  n.nspname AS schema,
  p.proname AS name,
  pg_get_function_identity_arguments(p.oid) AS args,
  CASE p.prokind
    WHEN 'f' THEN 'function'
    WHEN 'p' THEN 'procedure'
    WHEN 'a' THEN 'aggregate'
    WHEN 'w' THEN 'window'
    ELSE p.prokind::text
  END AS kind,
  l.lanname AS language
FROM pg_proc p
JOIN pg_namespace n ON n.oid = p.pronamespace
JOIN pg_language l ON l.oid = p.prolang
WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
ORDER BY 1, 2, 3;
