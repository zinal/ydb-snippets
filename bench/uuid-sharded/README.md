# Uuid::newSharded() benchmark

Experimental checks for the key generation scheme from [ydb-platform/ydb PR #45923](https://github.com/ydb-platform/ydb/pull/45923).

The scripts validate two claims of `Uuid::newSharded()`:

1. **Shard spread** — random 10-bit prefix (~1024 buckets) distributes writes across partition ranges.
2. **Time locality** — within a fixed prefix, keys sort by embedded epoch seconds.

Python code in `sharded_keygen.py` mirrors `ydb/library/yql/udfs/common/uuid/uuid_keygen.h`, so offline statistics match cluster behaviour.

## Prerequisites

### Offline (no cluster)

- Python 3.10+

### Cluster benchmarks

- YDB with Uuid UDF from PR #45923 (`Uuid::newSharded`, `Uuid::newChrono`, etc.)
- Python package `ydb` (see `requirements.txt`)
- Environment variables:

```bash
export YDB_ENDPOINT=grpc://localhost:2136
export YDB_DATABASE=/local
# auth: YDB_ACCESS_TOKEN_CREDENTIALS or YDB_USER/YDB_PASSWORD
export YDB_PROFILE=local   # optional; partition_analysis also works via SDK without it
```

Install dependencies:

```bash
pip install -r bench/uuid-sharded/requirements.txt
```

Create the benchmark table:

```bash
ydb -p "$YDB_PROFILE" yql -f bench/uuid-sharded/schema.yql
```

## Quick start

### 1. Offline prefix statistics (~seconds)

```bash
cd bench/uuid-sharded
./run_offline.sh 1000000
```

Or directly:

```bash
python3 offline_prefix_bench.py --mode sharded --count 1000000
python3 offline_prefix_bench.py --mode random  --count 1000000
python3 offline_prefix_bench.py --mode chrono   --count 1000000
```

**Pass criteria (sharded mode):**

| Metric | Expected |
|--------|----------|
| `duplicate_count` | 0 |
| `p_value_approx` (χ² vs uniform) | > 0.01 |
| `imbalance_ratio` across 1024 buckets | ≤ 1.15 |
| `sort_order_ok` | `True` |

Compare with `chrono`: prefix imbalance should be much higher (recent keys cluster in a narrow range).

### 2. Cluster write benchmark

```bash
cd bench/uuid-sharded
./run_cluster.sh
```

Environment overrides:

```bash
export UUID_BENCH_TABLE=bench_uuid
export UUID_BENCH_WORKERS=20
export UUID_BENCH_ROWS=100000
export SKIP_SCHEMA=1   # if table already exists
```

Runs three load profiles and saves JSON under `results/`:

| Mode | Generator | Purpose |
|------|-----------|---------|
| `random` | `RandomUuid($dep)` | Baseline spread |
| `chrono` | `Uuid::newChrono($dep)` | Hot-tail control |
| `sharded` | `Uuid::newSharded($dep)` | Target scheme |

### 3. Partition / prefix analysis after load

```bash
python3 partition_analysis.py \
  --table bench_uuid \
  --profile "$YDB_PROFILE" \
  --sample-prefixes 50000 \
  --sample-prefixes 50000 \
  --output results/partitions.json
```

Reports:

- `partition_count` — active datashards after load
- `prefix_sample.distinct_prefixes_in_sample` — prefix diversity in sample
- `prefix_sample.imbalance_ratio` — max/min bucket counts in sample
- `prefix_sample.gini` — inequality (lower is better for load balance)

Remove default skip and pass `--with-counts` to run `COUNT(*)` per partition key range (slow on large tables).

### 4. Full comparison report

```bash
python3 compare_all.py --offline-count 1000000 --output-dir results
python3 compare_all.py --cluster --workers 20 --rows 100000 --profile "$YDB_PROFILE"
```

Writes `results/report.json` with offline stats and optional cluster load numbers.

## Script reference

| File | Role |
|------|------|
| `sharded_keygen.py` | Python port of `MakeShardedUuidBytes` / prefix extraction |
| `offline_prefix_bench.py` | χ² test, Gini, imbalance, sort-order check |
| `load_bench.py` | Parallel UPSERT benchmark (Random/Chrono/Sharded) |
| `partition_analysis.py` | Sample prefix distribution + optional per-shard counts |
| `compare_all.py` | Orchestrator for offline + cluster runs |
| `schema.yql` | Row table with auto-partitioning |
| `run_offline.sh` | Smoke test without YDB |
| `run_cluster.sh` | End-to-end cluster benchmark |

## Interpreting cluster results

**Good signs for `newSharded`:**

- `tps` within ~10% of `random`
- `latency_ms_p99` clearly below `chrono` under the same load
- `prefix_sample.imbalance_ratio` ≤ 1.5 and `gini` close to `random`

**Warning signs:**

- `sharded` TPS or tail latency matches `chrono` → prefix may not affect leading sort bytes
- `prefix_sample.distinct_prefixes_in_sample` ≪ 1024 on large samples → investigate UDF build or generator regression
- High `gini` with low partition count → consider raising `AUTO_PARTITIONING_MIN_PARTITIONS_COUNT`

## Related PR unit tests

Upstream PR already covers correctness:

```bash
./ya make --build relwithdebinfo -tA ydb/library/yql/udfs/common/uuid/test
./ya make --build relwithdebinfo -tA ydb/library/yql/udfs/common/uuid/ut
```

These snippets focus on **effectiveness** (distribution and load balance), not UDF correctness.

Note: YQL `RandomUuid()` requires at least one dependency argument (e.g. `RandomUuid($dep)`); the load benchmark passes a per-row `$dep` for that reason.
