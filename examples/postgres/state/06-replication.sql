-- Репликация / WAL (если применимо)
-- Usage: psql -f state/06-replication.sql

\echo === recovery / timeline ===
SELECT
  pg_is_in_recovery() AS in_recovery,
  CASE WHEN pg_is_in_recovery()
    THEN pg_last_wal_receive_lsn()
    ELSE pg_current_wal_lsn()
  END AS wal_lsn;

\echo === replication slots ===
SELECT
  slot_name,
  slot_type,
  database,
  active,
  restart_lsn,
  confirmed_flush_lsn,
  wal_status,
  safe_wal_size
FROM pg_replication_slots
ORDER BY slot_name;

\echo === replication connections (primary view) ===
SELECT
  pid,
  usename,
  application_name,
  client_addr,
  state,
  sync_state,
  write_lag,
  flush_lag,
  replay_lag
FROM pg_stat_replication
ORDER BY application_name, client_addr;
