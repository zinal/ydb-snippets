-- Расширения, схемы, роли
-- Usage: psql -f state/02-extensions-schemas-roles.sql

\echo === extensions ===
SELECT e.extname, e.extversion, n.nspname AS schema, c.description
FROM pg_extension e
JOIN pg_namespace n ON n.oid = e.extnamespace
LEFT JOIN pg_description c ON c.objoid = e.oid AND c.classoid = 'pg_extension'::regclass
ORDER BY e.extname;

\echo === schemas (non-system) ===
SELECT nspname AS schema, pg_get_userbyid(nspowner) AS owner
FROM pg_namespace
WHERE nspname NOT IN ('pg_catalog', 'information_schema')
  AND nspname NOT LIKE 'pg_toast%'
  AND nspname NOT LIKE 'pg_temp%'
ORDER BY nspname;

\echo === roles ===
SELECT
  r.rolname,
  r.rolsuper,
  r.rolcreaterole,
  r.rolcreatedb,
  r.rolcanlogin,
  r.rolreplication,
  r.rolconnlimit,
  ARRAY(
    SELECT b.rolname
    FROM pg_auth_members m
    JOIN pg_roles b ON b.oid = m.roleid
    WHERE m.member = r.oid
    ORDER BY 1
  ) AS member_of
FROM pg_roles r
ORDER BY r.rolname;
