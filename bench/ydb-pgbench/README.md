## YDB pgbench-style workload with `ydb-bench`

This directory contains the results of a series of pgbench-style benchmarks executed against YDB using the `ydb-bench` Python tool. The standard pgbench TPC-B–like workload was extended with two custom SQL scripts, `wd01.sql` and `wd02.sql`, to exercise additional business logic and multi-table joins on top of the base benchmark.

### Workload description

- **Base tool**: `ydb-bench` (pgbench-compatible driver)
- **Custom statements**:
  - **`wd01.sql`**: write-heavy transaction that:
    - Updates account balance (`accounts.abalance`)
    - Reads the updated account
    - Updates teller and branch balances (`tellers.tbalance`, `branches.bbalance`)
    - Inserts a row into `history` with the transaction metadata and `CurrentUtcTimestamp()`
  - **`wd02.sql`**: read-heavy query that:
    - Joins `accounts`, `branches`, and `tellers` (via `teller_branch` view) on `bid`
    - Returns account balance along with corresponding branch and teller balances
- **Mix**: each run uses `--file workload/wd01.sql@3 --file workload/wd02.sql@1`, i.e. a 3:1 ratio of `wd01` to `wd02` (75% write / 25% read transactions).

### Test environment

- **Cluster**:
  - 9 physical hosts
  - Each host: 2 × Intel(R) Xeon(R) Gold 6230 @ 2.10 GHz (40 physical cores / 80 threads total per host)
  - 512 GB RAM
  - 4 × NVMe 2.9 TB
- **YDB**:
  - Version: `25.1.4.ent.4`
  - 9 storage nodes
  - 27 database nodes (3 per host)
  - Tables configured with **auto-split partitioning**, allowing shards to adapt to workload growth.

### Load patterns and files

Each `*.txt` file in this directory contains the full `ydb-bench` output for a particular concurrency level. Filenames encode the approximate configuration in the form:

- `00-5x10.txt` … `01-5x10.txt`: 5 client processes × 10 jobs
- `02-10x10.txt`: 10 × 10
- `03-15x10.txt`: 15 × 10
- `04-20x10.txt`: 20 × 10
- `05-25x10.txt`: 25 × 10
- `06-30x10.txt`: 30 × 10
- `07-35x10.txt`: 35 × 10
- `08-40x10.txt`: 40 × 10
- `09-25x10.txt` … `13-50x10.txt`: additional repetitions at intermediate loads
- `14-100x10.txt`: 100 × 10, 240-second run, used to probe saturation behavior

Most runs use a 120-second duration; the heaviest runs (`13-50x10.txt`, `14-100x10.txt`) use 240 seconds to stabilize metrics.

Each result file includes:

- Overall summary metrics: total transactions, TPS, success/failure counts
- Per-workload sections for `wd01.sql` and `wd02.sql`
- Latency statistics (average, min, max, P50, P95, P99) for:
  - Client-side duration
  - Server-side duration
  - CPU time

### Throughput scaling

When increasing concurrency, the cluster demonstrates strong linear or near-linear scaling in total TPS up to roughly 35–40 processes, with diminishing returns beyond that point:

- **Low concurrency (5 × 10)**:
  - ~4.0–4.1 K TPS total (`00-5x10.txt`, `01-5x10.txt`)
- **Medium concurrency (10–20 × 10)**:
  - At **10 × 10**: ~7.0 K TPS total (`02-10x10.txt`)
  - At **15 × 10**: ~10.0 K TPS total (`03-15x10.txt`)
  - At **20 × 10**: ~12.4 K TPS total (`04-20x10.txt`)
- **Near-optimal concurrency (25–40 × 10)**:
  - **25 × 10**: ~17.5 K–17.9 K TPS (`05-25x10.txt`, `09-25x10.txt`)
  - **30 × 10**: ~19.1–19.5 K TPS (`06-30x10.txt`, `10-30x10.txt`)
  - **35 × 10**: ~20.6–20.7 K TPS (`07-35x10.txt`, `11-35x10.txt`)
  - **40 × 10**: ~21.5–21.6 K TPS (`08-40x10.txt`, `12-40x10.txt`)
- **High concurrency / saturation (50–100 × 10)**:
  - **50 × 10**: ~22.6 K TPS (`13-50x10.txt`)
  - **100 × 10**: ~25.1 K TPS (`14-100x10.txt`)

From 5 to about 35–40 processes, each step increases TPS by roughly 1.5–2.0 K, showing good utilization of the multi-node YDB cluster. After ~40 processes, additional client concurrency yields smaller, sub-linear gains (from ~21.6 K to ~25.1 K TPS when going from 40 to 100 processes), indicating the system is approaching saturation either at the storage layer, CPU, or internal contention points.

### Workload split and per-query behavior

Across all runs, the 3:1 mix between `wd01` and `wd02` is preserved. The per-query metrics highlight complementary behavior:

- **`wd01.sql` (write-heavy, multi-table + history insert)**:
  - Delivers the majority of TPS (e.g. at 100 × 10: ~18.8 K TPS for `wd01` out of ~25.1 K total).
  - Average server latency typically in the **15–37 ms** range depending on load.
  - P95 server latencies generally stay below **~55 ms** up to 40 processes, increasing under heavier load but remaining under **~110 ms** even at 100 × 10.
  - Occasional failures at higher concurrency (tens to low hundreds of failed transactions at 25, 30, 35, 40, 50, and 100 processes) suggest transient contention or backpressure, but successful TPS remains high.

- **`wd02.sql` (read-heavy multi-join)**:
  - Runs at a lower absolute TPS due to the 1/4 workload share, e.g. ~5.4–6.3 K TPS across 40–100 processes.
  - Average server latency is noticeably lower than `wd01`, often in the **6–18 ms** range.
  - Tail latency is also better: P95 typically under **30 ms** and P99 often under **50 ms**, even at high concurrency.
  - No failed transactions were observed in the sampled runs, indicating that read-heavy joins are stable and resilient under load.

The combination shows that YDB can sustain a mixed workload where heavy transactional updates and multi-join reads coexist without the read path being significantly penalized by write pressure.

### Latency characteristics

Latency statistics across the runs show:

- **Client vs. server time**:
  - Client-side latencies are consistently a few milliseconds higher than server-side, accounting for network RTT, driver overhead, and client scheduling.
  - The gap remains small and stable, which indicates that most of the time is spent in actual server processing rather than client or network bottlenecks.
- **Scaling impact**:
  - As concurrency increases, **average latency grows moderately**, but the growth is slower than TPS growth up to ~35–40 processes.
  - At the highest loads (50–100 × 10), average and P95 latencies increase, reflecting saturation, but remain within acceptable limits for many OLTP-style workloads.
- **CPU time**:
  - Reported CPU time per operation is relatively low (around **1–3.5 ms**), even as total TPS grows.
  - This points to efficient execution on the YDB side and suggests that bottlenecks, when they appear, are more likely related to I/O, internal synchronization, or queueing rather than raw CPU capacity.

### Key performance insights

- **Good scaling up to ~35–40 concurrent processes**: TPS increases nearly linearly from ~4 K TPS at 5 × 10 to ~21–22 K TPS at 40 × 10, demonstrating that YDB can efficiently utilize a 9-host, 27-database-node cluster for mixed OLTP workloads.
- **Saturation behavior beyond 40 processes**: Pushing concurrency further to 50 and 100 processes yields smaller incremental TPS gains (up to ~25 K TPS), with higher tail latencies and a modest increase in failed write transactions, which is typical saturation behavior.
- **Stable mixed workload performance**: Read-heavy join queries (`wd02.sql`) maintain low latency and zero failures even when co-running with heavy write transactions (`wd01.sql`), showing that YDB’s MVCC and partitioning strategies handle read/write interference well.
- **Efficient CPU utilization**: Low per-operation CPU times, combined with high TPS, indicate good engine efficiency; scaling is primarily constrained by global resources (I/O, coordination) rather than per-core throughput.

Altogether, these tests show that a YDB cluster of this size can sustain **~20–25 K TPS** for a pgbench-like, write-dominated workload with additional business logic and joins, while keeping latencies in the low tens of milliseconds and preserving read performance under load.
