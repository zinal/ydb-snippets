#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

: "${YDB_ENDPOINT:?Set YDB_ENDPOINT}"
: "${YDB_DATABASE:?Set YDB_DATABASE}"

TABLE="${UUID_BENCH_TABLE:-bench_uuid}"
WORKERS="${UUID_BENCH_WORKERS:-20}"
ROWS="${UUID_BENCH_ROWS:-100000}"
PROFILE="${YDB_PROFILE:-}"

if [[ "${SKIP_SCHEMA:-0}" != "1" ]]; then
  echo "Creating table ${TABLE} (set SKIP_SCHEMA=1 to skip)..."
  ydb ${PROFILE:+-p "$PROFILE"} yql -f schema.yql
fi

mkdir -p results

for mode in random chrono sharded; do
  echo "Load benchmark: ${mode}"
  python3 load_bench.py \
    --mode "${mode}" \
    --table "${TABLE}" \
    --workers "${WORKERS}" \
    --rows "${ROWS}" \
    --output "results/load_${mode}.json"
done

echo "Partition / prefix analysis..."
python3 partition_analysis.py \
  --table "${TABLE}" \
  ${PROFILE:+--profile "$PROFILE"} \
  --sample-prefixes 50000 \
  --output results/partitions.json

python3 compare_all.py --offline-count 100000 --output-dir results

echo "Done. See results/"
