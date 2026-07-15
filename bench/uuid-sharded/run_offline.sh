#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

python3 offline_prefix_bench.py --mode sharded --count "${1:-1000000}"
python3 offline_prefix_bench.py --mode random --count "${1:-1000000}"
python3 offline_prefix_bench.py --mode chrono --count "${1:-1000000}"

echo
echo "Sort-order check (fixed prefix, 3600 steps):"
python3 - <<'PY'
from offline_prefix_bench import check_sharded_sort_order
print("sort_order_ok=", check_sharded_sort_order(42, 3600))
PY
