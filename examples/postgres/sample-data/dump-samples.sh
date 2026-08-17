#!/usr/bin/env bash
# Выгрузка образцов строк из указанных таблиц в CSV.
# Usage:
#   ./sample-data/dump-samples.sh public.users public.orders
#   LIMIT=50 ./sample-data/dump-samples.sh app.events
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${OUT_DIR:-$ROOT/out/samples}"
LIMIT="${LIMIT:-100}"
mkdir -p "$OUT_DIR"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 schema.table [schema.table ...]" >&2
  echo "Env: LIMIT (default 100), OUT_DIR, PG*" >&2
  exit 1
fi

: "${PGDATABASE:?PGDATABASE is required}"

quote_ident() {
  # "schema"."table" from schema.table (simple identifiers)
  local fq="$1"
  local schema="${fq%%.*}"
  local table="${fq#*.}"
  if [[ "$schema" == "$fq" || -z "$table" || "$table" == *.* ]]; then
    echo "Expected schema.table, got: $fq" >&2
    exit 1
  fi
  printf '"%s"."%s"' "${schema//\"/\"\"}" "${table//\"/\"\"}"
}

for fq in "$@"; do
  rel="$(quote_ident "$fq")"
  safe_name="${fq//./_}"
  out="$OUT_DIR/${safe_name}.sample-${LIMIT}.csv"
  echo "Sampling $fq (LIMIT $LIMIT) → $out"
  psql -v ON_ERROR_STOP=1 -c \
    "COPY (SELECT * FROM ${rel} LIMIT ${LIMIT}) TO STDOUT WITH (FORMAT csv, HEADER true)" \
    >"$out"
done

echo "Done. Files in $OUT_DIR"
