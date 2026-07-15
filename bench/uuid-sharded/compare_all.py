#!/usr/bin/env python3
"""Run offline and optional cluster benchmarks for uuid-sharded key generators."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run_offline(count: int) -> dict:
    results = {}
    for mode in ("random", "chrono", "sharded", "sharded_prefix"):
        command = [
            sys.executable,
            str(ROOT / "offline_prefix_bench.py"),
            "--mode",
            mode,
            "--count",
            str(count),
            "--json",
        ]
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
        results[mode] = json.loads(completed.stdout)
    return {"offline": results}


def run_cluster_load(mode: str, workers: int, rows: int, table: str, output_dir: Path) -> dict:
    output = output_dir / f"load_{mode}.json"
    command = [
        sys.executable,
        str(ROOT / "load_bench.py"),
        "--mode",
        mode,
        "--workers",
        str(workers),
        "--rows",
        str(rows),
        "--table",
        table,
        "--output",
        str(output),
    ]
    subprocess.run(command, check=True)
    return json.loads(output.read_text(encoding="utf-8"))


def run_partition_analysis(table: str, profile: str | None, output_dir: Path) -> dict:
    output = output_dir / "partitions.json"
    command = [
        sys.executable,
        str(ROOT / "partition_analysis.py"),
        "--table",
        table,
        "--sample-prefixes",
        "50000",
        "--output",
        str(output),
    ]
    if profile:
        command.extend(["--profile", profile])
    subprocess.run(command, check=True)
    return json.loads(output.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline-count", type=int, default=1_000_000)
    parser.add_argument("--cluster", action="store_true", help="Also run YDB load benchmarks")
    parser.add_argument("--workers", type=int, default=20)
    parser.add_argument("--rows", type=int, default=100_000)
    parser.add_argument("--table", default="bench_uuid")
    parser.add_argument("--profile", default=None, help="ydb CLI profile for scheme describe")
    parser.add_argument("--output-dir", default="results")
    args = parser.parse_args()

    output_dir = ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    report: dict = run_offline(args.offline_count)

    if args.cluster:
        cluster = {"load": {}, "partitions": {}}
        for mode in ("random", "chrono", "sharded"):
            cluster["load"][mode] = run_cluster_load(
                mode, args.workers, args.rows, args.table, output_dir
            )
        cluster["partitions"] = run_partition_analysis(args.table, args.profile, output_dir)
        report["cluster"] = cluster

    report_path = output_dir / "report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(report_path.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
