"""Python port of MakeShardedUuidBytes / MakeChronoUuidBytes from ydb-platform/ydb PR #45923.

The logic mirrors ydb/library/yql/udfs/common/uuid/uuid_keygen.h so offline analysis
matches what Uuid::newSharded() and Uuid::newChrono() produce on a cluster.
"""

from __future__ import annotations

import secrets
import struct
import time
from typing import Iterable

UUID_LEN = 16

PREFIX_BITS = 10
SHARDED_TIMESTAMP_BITS = 30
PREFIX_MSB_MASK = ((1 << PREFIX_BITS) - 1) << (64 - PREFIX_BITS)
PREFIX_PARAM_MASK = (1 << PREFIX_BITS) - 1
SHARDED_TIMESTAMP_SHIFT = 64 - PREFIX_BITS - SHARDED_TIMESTAMP_BITS
SHARDED_TIMESTAMP_MASK = ((1 << SHARDED_TIMESTAMP_BITS) - 1) << SHARDED_TIMESTAMP_SHIFT

UUID_VERSION_BYTE = 0x80
PREFIX_BUCKET_COUNT = 1 << PREFIX_BITS


def read_be64(data: bytes | bytearray, offset: int = 0) -> int:
    return struct.unpack_from(">Q", data, offset)[0]


def write_be64(value: int, data: bytearray, offset: int = 0) -> None:
    struct.pack_into(">Q", data, offset, value & 0xFFFFFFFFFFFFFFFF)


def fill_random_bytes(data: bytearray) -> None:
    data[:] = secrets.token_bytes(len(data))


def set_uuid_version_and_variant(result: bytearray) -> None:
    result[7] = (result[7] & 0x0F) | UUID_VERSION_BYTE
    result[8] = (result[8] & 0x3F) | 0x80


def prefix_param_to_msb(prefix: int) -> int:
    return (prefix & PREFIX_PARAM_MASK) << (64 - PREFIX_BITS)


def extract_prefix_from_uuid_bytes(data: bytes | bytearray) -> int:
    msb = read_be64(data, 0)
    return (msb & PREFIX_MSB_MASK) >> (64 - PREFIX_BITS)


def get_timestamp_code(epoch_seconds: int) -> int:
    return (epoch_seconds % (1 << SHARDED_TIMESTAMP_BITS)) << SHARDED_TIMESTAMP_SHIFT


def update_msb_sharded(msb: int, prefix: int, epoch_seconds: int, has_prefix: bool) -> int:
    ts_code = get_timestamp_code(epoch_seconds)
    if has_prefix:
        return (
            (msb & ~(PREFIX_MSB_MASK | SHARDED_TIMESTAMP_MASK))
            | (prefix_param_to_msb(prefix) | (ts_code & SHARDED_TIMESTAMP_MASK))
        )
    return (msb & ~SHARDED_TIMESTAMP_MASK) | (ts_code & SHARDED_TIMESTAMP_MASK)


def update_msb_chrono(result: bytearray, prefix: int) -> None:
    msb = read_be64(result, 0)
    msb = (msb & ~PREFIX_MSB_MASK) | prefix_param_to_msb(prefix)
    write_be64(msb, result, 0)


def make_sharded_uuid_bytes(
    prefix: int,
    epoch_seconds: int | None = None,
    has_prefix: bool = False,
) -> bytes:
    if epoch_seconds is None:
        epoch_seconds = int(time.time())
    result = bytearray(UUID_LEN)
    fill_random_bytes(result)
    set_uuid_version_and_variant(result)
    msb = read_be64(result, 0)
    msb = update_msb_sharded(msb, prefix, epoch_seconds, has_prefix)
    write_be64(msb, result, 0)
    return bytes(result)


def make_chrono_uuid_bytes(
    prefix: int,
    timestamp_ms: int | None = None,
    has_prefix: bool = False,
) -> bytes:
    if timestamp_ms is None:
        timestamp_ms = int(time.time() * 1000)
    result = bytearray(UUID_LEN)
    fill_random_bytes(result)
    result[0] = (timestamp_ms >> 40) & 0xFF
    result[1] = (timestamp_ms >> 32) & 0xFF
    result[2] = (timestamp_ms >> 24) & 0xFF
    result[3] = (timestamp_ms >> 16) & 0xFF
    result[4] = (timestamp_ms >> 8) & 0xFF
    result[5] = timestamp_ms & 0xFF
    set_uuid_version_and_variant(result)
    if has_prefix:
        update_msb_chrono(result, prefix)
    return bytes(result)


def make_random_uuid_bytes() -> bytes:
    return secrets.token_bytes(UUID_LEN)


def compare_uuid_bytes(lhs: bytes, rhs: bytes) -> int:
    for left, right in zip(lhs, rhs):
        if left < right:
            return -1
        if left > right:
            return 1
    return 0


def uuid_bytes_to_hex(data: bytes | bytearray) -> str:
    return data.hex()


def iter_sharded_prefixes(values: Iterable[bytes]) -> Iterable[int]:
    for value in values:
        yield extract_prefix_from_uuid_bytes(value)


def gini_coefficient(values: list[int]) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    total = sum(sorted_values)
    if total == 0:
        return 0.0
    n = len(sorted_values)
    weighted = 0.0
    for index, value in enumerate(sorted_values, start=1):
        weighted += index * value
    return (2.0 * weighted) / (n * total) - (n + 1.0) / n


def imbalance_ratio(values: list[int]) -> float:
    positive = [value for value in values if value > 0]
    if not positive:
        return 0.0
    return max(positive) / min(positive)
