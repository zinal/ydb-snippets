#!/usr/bin/env python3
"""Analyze row distribution across YDB table partitions for uuid-sharded benchmarks."""

from __future__ import annotations

import argparse
import json
import logging
import math
import subprocess
import sys
from pathlib import Path

import ydb

from sharded_keygen import (
    PREFIX_BUCKET_COUNT,
    extract_prefix_from_uuid_bytes,
    gini_coefficient,
    imbalance_ratio,
)
from ydb_connect import connect_driver, table_path


def load_scheme_describe(table: str, profile: str | None, describe_json: Path | None) -> dict:
    if describe_json is not None:
        return json.loads(describe_json.read_text(encoding="utf-8"))
    if not profile:
        raise RuntimeError("Provide --profile or --describe-json")
    command = [
        "ydb",
        "-p",
        profile,
        "scheme",
        "describe",
        table,
        "--format",
        "json",
    ]
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(completed.stdout)


def partition_ranges(describe: dict) -> list[dict]:
    partitions = describe.get("PathDescription", {}).get("TablePartitions", [])
    ranges: list[dict] = []
    for partition in partitions:
        key_range = partition.get("KeyRange", {})
        ranges.append(
            {
                "datashard_id": partition.get("DatashardId"),
                "from": key_range.get("From"),
                "to": key_range.get("To"),
            }
        )
    return ranges


def decode_uuid_key(value: dict | None) -> bytes | None:
    if not value:
        return None
    # ydb scheme describe returns typed key components; Uuid is usually under "Uuid" or raw bytes.
    if "Uuid" in value:
        raw = value["Uuid"]
        if isinstance(raw, str):
            return bytes.fromhex(raw.replace("-", ""))
        if isinstance(raw, (bytes, bytearray)):
            return bytes(raw)
    if "Value" in value and isinstance(value["Value"], str):
        text = value["Value"]
        if len(text) == 32:
            return bytes.fromhex(text)
    return None


def count_rows_in_range(pool: ydb.SessionPool, table: str, lower: bytes | None, upper: bytes | None) -> int:
    query_parts = [f"SELECT COUNT(*) AS cnt FROM `{table}`"]
    params: dict[str, object] = {}
    if lower is not None or upper is not None:
        query_parts.append("WHERE")
        clauses: list[str] = []
        if lower is not None:
            clauses.append("id >= $lo")
            params["$lo"] = lower
        if upper is not None:
            clauses.append("id < $hi")
            params["$hi"] = upper
        query_parts.append(" AND ".join(clauses))
    query = "\n".join(query_parts) + ";"

    def callee(session: ydb.Session) -> int:
        prepared = session.prepare(query)
        result = session.transaction(ydb.OnlineReadOnly()).execute(prepared, params)
        return int(result[0].rows[0].cnt)

    return pool.retry_operation_sync(callee)


def sample_prefix_distribution(pool: ydb.SessionPool, table: str, sample_size: int) -> dict:
    query = f"""
    SELECT id
    FROM `{table}`
    LIMIT {sample_size};
    """

    def callee(session: ydb.Session) -> list[bytes]:
        prepared = session.prepare(query)
        result = session.transaction(ydb.OnlineReadOnly()).execute(prepared, {})
        ids: list[bytes] = []
        for row in result[0].rows:
            raw = row.id
            if isinstance(raw, (bytes, bytearray)):
                ids.append(bytes(raw))
        return ids

    ids = pool.retry_operation_sync(callee)
    prefixes = [extract_prefix_from_uuid_bytes(value) for value in ids]
    counts: dict[int, int] = {}
    for prefix in prefixes:
        counts[prefix] = counts.get(prefix, 0) + 1
    bucket_values = [counts.get(bucket, 0) for bucket in range(PREFIX_BUCKET_COUNT)]
    return {
        "sample_size": len(ids),
        "distinct_prefixes_in_sample": len(counts),
        "imbalance_ratio": imbalance_ratio(bucket_values) if any(bucket_values) else 0.0,
        "gini": gini_coefficient(bucket_values) if any(bucket_values) else 0.0,
    }


def analyze(args: argparse.Namespace) -> dict:
    table = table_path(args.table)
    describe = load_scheme_describe(table, args.profile, args.describe_json)
    ranges = partition_ranges(describe)

    result: dict = {
        "table": table,
        "partition_count": len(ranges),
        "partitions": [],
    }

    if args.sample_prefixes > 0:
        driver = connect_driver()
        pool = ydb.SessionPool(driver, size=4)
        result["prefix_sample"] = sample_prefix_distribution(pool, args.table, args.sample_prefixes)

    if not args.skip_counts:
        driver = connect_driver()
        pool = ydb.SessionPool(driver, size=min(8, max(1, len(ranges))))
        counts: list[int] = []
        for item in ranges:
            lower = decode_uuid_key(item.get("from"))
            upper = decode_uuid_key(item.get("to"))
            count = count_rows_in_range(pool, args.table, lower, upper)
            counts.append(count)
            item["row_count"] = count
            logging.info(
                "datashard=%s rows=%s from=%s to=%s",
                item["datashard_id"],
                count,
                item.get("from"),
                item.get("to"),
            )
        result["partitions"] = ranges
        result["row_count_total"] = sum(counts)
        result["imbalance_ratio"] = imbalance_ratio(counts)
        result["gini"] = gini_coefficient(counts)
        result["entropy_bits"] = shannon_entropy_bits(counts)

    return result


def shannon_entropy_bits(counts: list[int]) -> float:
    total = sum(counts)
    if total == 0:
        return 0.0
    entropy = 0.0
    for count in counts:
        if count <= 0:
            continue
        probability = count / total
        entropy -= probability * math.log2(probability)
    return entropy


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("ydb").setLevel(logging.WARNING)

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--table", default="bench_uuid")
    parser.add_argument("--profile", default=None, help="ydb CLI profile for scheme describe")
    parser.add_argument("--describe-json", type=Path, default=None, help="Offline scheme describe JSON")
    parser.add_argument("--sample-prefixes", type=int, default=50_000, help="Rows to scan for prefix stats")
    parser.add_argument(
        "--with-counts",
        action="store_true",
        help="Run per-partition COUNT (slow on large tables)",
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    if not args.with_counts:
        args.skip_counts = True
    else:
        args.skip_counts = False

    result = analyze(args)
    payload = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
