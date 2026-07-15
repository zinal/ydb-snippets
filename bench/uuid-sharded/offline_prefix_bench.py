#!/usr/bin/env python3
"""Offline statistical checks for Uuid::newSharded() prefix spread and sort order."""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import Counter

from sharded_keygen import (
    PREFIX_BUCKET_COUNT,
    compare_uuid_bytes,
    extract_prefix_from_uuid_bytes,
    gini_coefficient,
    imbalance_ratio,
    make_chrono_uuid_bytes,
    make_random_uuid_bytes,
    make_sharded_uuid_bytes,
    uuid_bytes_to_hex,
)


def chi_square_uniform(counts: Counter[int], bucket_count: int) -> tuple[float, float]:
    """Return (chi2 statistic, p-value approximation via Wilson-Hilferty)."""
    total = sum(counts.values())
    expected = total / bucket_count
    chi2 = 0.0
    for bucket in range(bucket_count):
        observed = counts.get(bucket, 0)
        diff = observed - expected
        chi2 += (diff * diff) / expected

    # Normal approximation for large df (1023).
    df = bucket_count - 1
    z = ((chi2 / df) ** (1.0 / 3.0) - (1.0 - 2.0 / (9.0 * df))) / math.sqrt(2.0 / (9.0 * df))
    # One-sided upper tail: P(X > chi2) ≈ 1 - Φ(z).
    p_value = 0.5 * math.erfc(z / math.sqrt(2.0))
    return chi2, p_value


def generate_keys(mode: str, count: int, fixed_prefix: int | None) -> list[bytes]:
    epoch = int(time.time())
    keys: list[bytes] = []
    for index in range(count):
        if mode == "sharded":
            keys.append(make_sharded_uuid_bytes(0, epoch + (index // 1000), False))
        elif mode == "sharded_prefix":
            prefix = fixed_prefix if fixed_prefix is not None else index % PREFIX_BUCKET_COUNT
            keys.append(make_sharded_uuid_bytes(prefix, epoch + index, True))
        elif mode == "chrono":
            keys.append(make_chrono_uuid_bytes(0, (epoch * 1000) + index, False))
        elif mode == "random":
            keys.append(make_random_uuid_bytes())
        else:
            raise ValueError(f"Unknown mode: {mode}")
    return keys


def analyze_prefix_distribution(keys: list[bytes]) -> dict:
    prefixes = [extract_prefix_from_uuid_bytes(key) for key in keys]
    counts = Counter(prefixes)
    bucket_values = [counts.get(bucket, 0) for bucket in range(PREFIX_BUCKET_COUNT)]
    chi2, p_value = chi_square_uniform(counts, PREFIX_BUCKET_COUNT)
    return {
        "samples": len(keys),
        "distinct_prefixes": len(counts),
        "expected_prefixes": PREFIX_BUCKET_COUNT,
        "chi2": chi2,
        "p_value_approx": p_value,
        "imbalance_ratio": imbalance_ratio(bucket_values),
        "gini": gini_coefficient(bucket_values),
        "min_bucket": min(bucket_values),
        "max_bucket": max(bucket_values),
        "mean_bucket": sum(bucket_values) / PREFIX_BUCKET_COUNT,
    }


def check_uniqueness(keys: list[bytes]) -> int:
    return len(keys) - len({uuid_bytes_to_hex(key) for key in keys})


def check_sharded_sort_order(prefix: int, steps: int) -> bool:
    epoch = 1_700_000_000
    previous = make_sharded_uuid_bytes(prefix, epoch, True)
    for offset in range(1, steps + 1):
        current = make_sharded_uuid_bytes(prefix, epoch + offset, True)
        if compare_uuid_bytes(previous, current) >= 0:
            return False
        previous = current
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("sharded", "sharded_prefix", "chrono", "random"),
        default="sharded",
        help="Key generation strategy to simulate",
    )
    parser.add_argument("--count", type=int, default=1_000_000, help="Number of UUIDs to generate")
    parser.add_argument("--prefix", type=int, default=None, help="Fixed prefix for sharded_prefix mode")
    parser.add_argument("--sort-steps", type=int, default=3600, help="Sort-order check span in seconds")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args()

    started = time.time()
    keys = generate_keys(args.mode, args.count, args.prefix)
    elapsed = time.time() - started

    duplicates = check_uniqueness(keys)
    stats = analyze_prefix_distribution(keys)
    stats["generation_seconds"] = elapsed
    stats["mode"] = args.mode
    stats["duplicate_count"] = duplicates
    stats["sort_order_ok"] = check_sharded_sort_order(args.prefix or 42, args.sort_steps)

    if args.json:
        print(json.dumps(stats, indent=2, sort_keys=True))
    else:
        print(f"mode={stats['mode']} samples={stats['samples']}")
        print(f"generation_seconds={stats['generation_seconds']:.3f}")
        print(f"duplicate_count={stats['duplicate_count']}")
        print(f"distinct_prefixes={stats['distinct_prefixes']} / {stats['expected_prefixes']}")
        print(f"chi2={stats['chi2']:.2f} p_value_approx={stats['p_value_approx']:.6f}")
        print(f"imbalance_ratio={stats['imbalance_ratio']:.3f} gini={stats['gini']:.4f}")
        print(f"bucket min/mean/max={stats['min_bucket']}/{stats['mean_bucket']:.1f}/{stats['max_bucket']}")
        print(f"sort_order_ok={stats['sort_order_ok']}")

    failed = duplicates != 0
    if args.mode in ("random", "sharded") and stats["p_value_approx"] < 0.01:
        failed = True
    if args.mode == "sharded" and not stats["sort_order_ok"]:
        failed = True
    stats["imbalance_limit_hint"] = 1.15 if args.count >= 1_000_000 else 2.5
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
