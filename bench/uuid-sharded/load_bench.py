#!/usr/bin/env python3
"""Write-load benchmark comparing RandomUuid, Uuid::newChrono, Uuid::newSharded."""

from __future__ import annotations

import argparse
import json
import logging
import os
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import ydb

from ydb_connect import connect_driver

KEY_GENERATORS = {
    "random": "RandomUuid($dep)",
    "chrono": "Uuid::newChrono($dep)",
    "sharded": "Uuid::newSharded($dep)",
    "sharded_prefix": "Uuid::newShardedPrefix($prefix, $dep)",
}

SINGLE_ROW_QUERIES = {
    "random": """
        DECLARE $dep AS Int32;
        UPSERT INTO `{table}` (id, payload, created_at)
        VALUES (RandomUuid($dep), RandomUuid($dep + 1), CurrentUtcTimestamp());
    """,
    "chrono": """
        DECLARE $dep AS Int32;
        UPSERT INTO `{table}` (id, payload, created_at)
        VALUES (Uuid::newChrono($dep), RandomUuid($dep + 1), CurrentUtcTimestamp());
    """,
    "sharded": """
        DECLARE $dep AS Int32;
        UPSERT INTO `{table}` (id, payload, created_at)
        VALUES (Uuid::newSharded($dep), RandomUuid($dep + 1), CurrentUtcTimestamp());
    """,
    "sharded_prefix": """
        DECLARE $dep AS Int32;
        DECLARE $prefix AS Uint64;
        UPSERT INTO `{table}` (id, payload, created_at)
        VALUES (Uuid::newShardedPrefix($prefix, $dep), RandomUuid($dep + 1), CurrentUtcTimestamp());
    """,
}


class LatencyTracker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.samples_ms: list[float] = []
        self.errors = 0
        self.rows = 0

    def add(self, latency_ms: float, row_count: int) -> None:
        with self._lock:
            self.samples_ms.append(latency_ms)
            self.rows += row_count

    def add_error(self) -> None:
        with self._lock:
            self.errors += 1

    def summary(self, elapsed_sec: float) -> dict:
        with self._lock:
            samples = list(self.samples_ms)
            rows = self.rows
            errors = self.errors
        if not samples:
            return {"rows": rows, "errors": errors, "tps": 0.0}
        samples.sort()
        def percentile(p: float) -> float:
            index = min(len(samples) - 1, int(len(samples) * p))
            return samples[index]
        return {
            "rows": rows,
            "errors": errors,
            "elapsed_sec": elapsed_sec,
            "tps": rows / elapsed_sec if elapsed_sec > 0 else 0.0,
            "latency_ms_avg": statistics.mean(samples),
            "latency_ms_p50": percentile(0.50),
            "latency_ms_p95": percentile(0.95),
            "latency_ms_p99": percentile(0.99),
            "latency_ms_max": samples[-1],
        }


def worker(
    pool: ydb.SessionPool,
    mode: str,
    table: str,
    batch_size: int,
    rows_target: int,
    prefix: int,
    worker_id: int,
    tracker: LatencyTracker,
    stop_event: threading.Event,
) -> None:
    query_template = SINGLE_ROW_QUERIES[mode].format(table=table)
    rows_written = 0

    def make_params(row_index: int) -> dict[str, object]:
        # Dependency arg breaks YQL constant folding for RandomUuid / Uuid::* generators.
        dep = worker_id * rows_target + row_index
        params: dict[str, object] = {"$dep": dep}
        if mode == "sharded_prefix":
            params["$prefix"] = prefix
        return params

    while not stop_event.is_set() and rows_written < rows_target:
        started = time.perf_counter()
        try:
            def callee(session: ydb.Session) -> None:
                prepared = session.prepare(query_template)
                tx = session.transaction(ydb.SerializableReadWrite())
                tx.execute(prepared, make_params(rows_written), commit_tx=True)

            pool.retry_operation_sync(callee)
            tracker.add((time.perf_counter() - started) * 1000.0, 1)
            rows_written += 1
        except Exception:
            logging.exception("write failed")
            tracker.add_error()


def run_benchmark(args: argparse.Namespace) -> dict:
    driver = connect_driver()
    pool = ydb.SessionPool(driver, size=args.workers + 2)
    tracker = LatencyTracker()
    stop_event = threading.Event()
    rows_per_worker = math_ceil_div(args.rows, args.workers)

    started = time.perf_counter()
    deadline = started + args.duration if args.duration > 0 else None

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [
            executor.submit(
                worker,
                pool,
                args.mode,
                args.table,
                args.batch_size,
                rows_per_worker,
                args.prefix,
                worker_index,
                tracker,
                stop_event,
            )
            for worker_index in range(args.workers)
        ]
        try:
            while True:
                if deadline is not None and time.perf_counter() >= deadline:
                    stop_event.set()
                    break
                if all(future.done() for future in futures):
                    break
                time.sleep(0.2)
        finally:
            stop_event.set()
            for future in as_completed(futures):
                future.result()

    elapsed = time.perf_counter() - started
    result = tracker.summary(elapsed)
    result["mode"] = args.mode
    result["workers"] = args.workers
    result["table"] = args.table
    result["generator"] = KEY_GENERATORS[args.mode]
    return result


def math_ceil_div(numerator: int, denominator: int) -> int:
    return (numerator + denominator - 1) // denominator


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("ydb").setLevel(logging.WARNING)

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=tuple(KEY_GENERATORS), default="sharded")
    parser.add_argument("--table", default=os.getenv("UUID_BENCH_TABLE", "bench_uuid"))
    parser.add_argument("--workers", type=int, default=20)
    parser.add_argument("--rows", type=int, default=100_000, help="Total rows across all workers")
    parser.add_argument("--duration", type=int, default=0, help="Optional time limit in seconds")
    parser.add_argument("--batch-size", type=int, default=1, help="Reserved for future batched UPSERT")
    parser.add_argument("--prefix", type=int, default=42, help="Prefix for sharded_prefix mode")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", default="", help="Optional JSON output file")
    args = parser.parse_args()

    result = run_benchmark(args)
    payload = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(payload + "\n")
    if args.json or not args.output:
        print(payload)
    return 0 if result["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
