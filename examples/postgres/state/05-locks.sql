-- Блокировки и ожидания
-- Usage: psql -f state/05-locks.sql

\echo === blocking tree (who blocks whom) ===
SELECT
  blocked.pid AS blocked_pid,
  blocked.usename AS blocked_user,
  left(blocked.query, 120) AS blocked_query,
  blocking.pid AS blocking_pid,
  blocking.usename AS blocking_user,
  left(blocking.query, 120) AS blocking_query,
  blocked.wait_event_type,
  blocked.wait_event,
  now() - blocked.query_start AS blocked_for
FROM pg_stat_activity blocked
JOIN pg_locks bl ON bl.pid = blocked.pid AND NOT bl.granted
JOIN pg_locks gl
  ON gl.locktype = bl.locktype
 AND gl.database IS NOT DISTINCT FROM bl.database
 AND gl.relation IS NOT DISTINCT FROM bl.relation
 AND gl.page IS NOT DISTINCT FROM bl.page
 AND gl.tuple IS NOT DISTINCT FROM bl.tuple
 AND gl.virtualxid IS NOT DISTINCT FROM bl.virtualxid
 AND gl.transactionid IS NOT DISTINCT FROM bl.transactionid
 AND gl.classid IS NOT DISTINCT FROM bl.classid
 AND gl.objid IS NOT DISTINCT FROM bl.objid
 AND gl.objsubid IS NOT DISTINCT FROM bl.objsubid
 AND gl.granted
JOIN pg_stat_activity blocking ON blocking.pid = gl.pid
WHERE blocked.pid <> blocking.pid
ORDER BY blocked.query_start;

\echo === ungranted locks ===
SELECT
  l.locktype,
  l.mode,
  l.granted,
  l.pid,
  a.usename,
  a.state,
  a.wait_event,
  COALESCE(n.nspname || '.' || c.relname, l.relation::text) AS relation,
  left(a.query, 120) AS query
FROM pg_locks l
LEFT JOIN pg_stat_activity a ON a.pid = l.pid
LEFT JOIN pg_class c ON c.oid = l.relation
LEFT JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE NOT l.granted
ORDER BY a.query_start NULLS LAST;
