#!/usr/bin/env bash
# Выгрузка DDL схемы текущей БД (PG* из окружения).
# Usage:
#   ./schema/dump-schema.sh
#   SCHEMAS='public app' ./schema/dump-schema.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${OUT_DIR:-$ROOT/out/schema}"
mkdir -p "$OUT_DIR"

DB="${PGDATABASE:?PGDATABASE is required}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BASE="$OUT_DIR/${DB}-schema-${STAMP}"

SCHEMA_ARGS=()
if [[ -n "${SCHEMAS:-}" ]]; then
  # shellcheck disable=SC2206
  for s in $SCHEMAS; do
    SCHEMA_ARGS+=(--schema="$s")
  done
fi
if [[ -n "${EXCLUDE_SCHEMAS:-}" ]]; then
  # shellcheck disable=SC2206
  for s in $EXCLUDE_SCHEMAS; do
    SCHEMA_ARGS+=(--exclude-schema="$s")
  done
fi

echo "Dumping schema of database '$DB' → ${BASE}.sql"
pg_dump \
  --schema-only \
  --no-owner \
  --no-privileges \
  --quote-all-identifiers \
  "${SCHEMA_ARGS[@]}" \
  -f "${BASE}.sql"

# Роли / tablespaces (может потребовать права суперпользователя)
if pg_dumpall --roles-only --no-role-passwords -f "${BASE}-globals.sql" 2>/dev/null; then
  echo "Globals (roles) → ${BASE}-globals.sql"
else
  echo "Skip globals dump (insufficient privileges or pg_dumpall unavailable)" >&2
  rm -f "${BASE}-globals.sql"
fi

# Удобный «latest» symlink
ln -sfn "$(basename "${BASE}.sql")" "$OUT_DIR/${DB}-schema-latest.sql"
echo "Latest link → $OUT_DIR/${DB}-schema-latest.sql"
