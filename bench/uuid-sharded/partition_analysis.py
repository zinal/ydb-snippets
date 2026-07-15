#!/usr/bin/env python3
"""Analyze row distribution across YDB table partitions for uuid-sharded benchmarks."""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
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
from ydb_connect import connect_driver


def build_ydb_cli_prefix(profile: str | None) -> list[str]:
    prefix = ["ydb"]
    profile = profile or os.getenv("YDB_PROFILE")
    if profile:
        prefix.extend(["-p", profile])
        return prefix

    endpoint = os.getenv("YDB_ENDPOINT")
    database = os.getenv("YDB_DATABASE")
    if endpoint:
        prefix.extend(["-e", endpoint])
    if database:
        prefix.extend(["-d", database])
    return prefix


def load_scheme_describe_cli(table: str, profile: str | None) -> dict:
    command = build_ydb_cli_prefix(profile) + [
        "scheme",
        "describe",
        table,
        "--format",
        "json",
    ]
    if len(command) <= 1 or command[0] != "ydb":
        raise RuntimeError("Failed to build ydb CLI command")

    has_target = profile or os.getenv("YDB_PROFILE") or os.getenv("YDB_ENDPOINT")
    if not has_target:
        raise RuntimeError("Set YDB_PROFILE or YDB_ENDPOINT/YDB_DATABASE for scheme describe")

    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(completed.stdout)


def partition_ranges_from_scheme_json(describe: dict) -> list[dict]:
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


def uuid_from_key_bound(bound: ydb.KeyBound | None) -> bytes | None:
    if bound is None:
        return None
    value = bound.value
    if isinstance(value, tuple):
        if not value:
            return None
        value = value[0]
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    return None


def partition_ranges_from_table_describe(driver: ydb.Driver, table: str) -> list[dict]:
    settings = ydb.DescribeTableSettings().with_include_shard_key_bounds(True)
    entry = driver.table_client.describe_table(table, settings)
    ranges: list[dict] = []
    for key_range in entry.shard_key_ranges:
        ranges.append(
            {
                "datashard_id": None,
                "from": uuid_from_key_bound(key_range.from_bound),
                "to": uuid_from_key_bound(key_range.to_bound),
                "source": "table_describe",
            }
        )
    return ranges


def load_partition_ranges(
    table: str,
    profile: str | None,
    describe_json: Path | None,
    driver: ydb.Driver,
) -> tuple[list[dict], str]:
    if describe_json is not None:
        describe = json.loads(describe_json.read_text(encoding="utf-8"))
        return partition_ranges_from_scheme_json(describe), "describe_json"

    try:
        describe = load_scheme_describe_cli(table, profile)
        return partition_ranges_from_scheme_json(describe), "ydb_cli"
    except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError, RuntimeError) as exc:
        logging.warning("ydb CLI scheme describe unavailable (%s), falling back to SDK", exc)

    return partition_ranges_from_table_describe(driver, table), "python_sdk"


def decode_uuid_key(value: object | None) -> bytes | None:
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    if not isinstance(value, dict):
        return None
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
    driver = connect_driver()
    pool = ydb.SessionPool(driver, size=8)
    ranges, partition_source = load_partition_ranges(
        args.table,
        args.profile,
        args.describe_json,
        driver,
    )

    result: dict = {
        "table": args.table,
        "partition_count": len(ranges),
        "partition_source": partition_source,
        "partitions": [],
    }

    if len(ranges) < 2:
        result["partition_metrics_reliable"] = False
        result["warnings"] = [
            "Table has fewer than 2 partitions. This is normal right after CREATE TABLE "
            "or with a small dataset: YDB keeps a single datashard until auto-split triggers.",
            "Per-partition imbalance/gini are not meaningful yet — rely on prefix_sample "
            "(logical 10-bit spread) or load more rows and rerun analysis.",
        ]
        logging.warning(
            "partition_count=%s: per-partition metrics skipped; use prefix_sample instead",
            len(ranges),
        )
    else:
        result["partition_metrics_reliable"] = True

    if args.sample_prefixes > 0:
        result["prefix_sample"] = sample_prefix_distribution(pool, args.table, args.sample_prefixes)

    if not args.skip_counts:
        if len(ranges) < 2:
            logging.warning("Skipping per-partition COUNT: need at least 2 partitions")
        else:
            counts: list[int] = []
            partition_rows: list[dict] = []
            for item in ranges:
                lower = decode_uuid_key(item.get("from"))
                upper = decode_uuid_key(item.get("to"))
                count = count_rows_in_range(pool, args.table, lower, upper)
                counts.append(count)
                partition_info = dict(item)
                partition_info["row_count"] = count
                partition_rows.append(partition_info)
                logging.info(
                    "datashard=%s rows=%s from=%s to=%s",
                    item.get("datashard_id"),
                    count,
                    item.get("from"),
                    item.get("to"),
                )
            result["partitions"] = partition_rows
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
    parser.add_argument(
        "--profile",
        default=os.getenv("YDB_PROFILE"),
        help="ydb CLI profile (optional; falls back to YDB_ENDPOINT/YDB_DATABASE or Python SDK)",
    )
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

    args.skip_counts = not args.with_counts

    result = analyze(args)
    payload = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
