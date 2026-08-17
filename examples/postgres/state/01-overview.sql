-- Обзор: версия, текущая сессия, базовые параметры инстанса
-- Usage: psql -f state/01-overview.sql

\echo === version / session ===
SELECT version();
SELECT
  current_database() AS db,
  current_user AS "user",
  session_user,
  inet_client_addr() AS client_addr,
  inet_server_addr() AS server_addr,
  inet_server_port() AS server_port,
  pg_postmaster_start_time() AS started_at,
  now() AS now_ts,
  pg_is_in_recovery() AS in_recovery;

\echo === cluster / database sizes ===
SELECT pg_size_pretty(sum(pg_database_size(datname))) AS all_db_size
FROM pg_database;

SELECT
  datname,
  pg_size_pretty(pg_database_size(datname)) AS size,
  datcollate,
  datctype
FROM pg_database
ORDER BY pg_database_size(datname) DESC;

\echo === key settings ===
SELECT name, setting, unit, short_desc
FROM pg_settings
WHERE name IN (
  'server_version',
  'server_version_num',
  'data_directory',
  'config_file',
  'max_connections',
  'shared_buffers',
  'work_mem',
  'maintenance_work_mem',
  'effective_cache_size',
  'wal_level',
  'max_wal_senders',
  'archive_mode',
  'archive_command',
  'hot_standby',
  'default_transaction_isolation',
  'timezone',
  'lc_collate',
  'lc_ctype'
)
ORDER BY name;
