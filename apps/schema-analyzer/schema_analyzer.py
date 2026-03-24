#!/usr/bin/env python3
import argparse
import logging
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import ydb
import ydb.iam


AuthMode = str
SchemaFingerprint = Tuple[
    int,  # column count
    Tuple[str, ...],  # sorted column types
    int,  # primary key column count
    Tuple[str, ...],  # primary key column types (order preserved)
    Tuple[Tuple[str, Tuple[str, ...], Tuple[str, ...]], ...],  # sorted index signatures
]


@dataclass(frozen=True)
class ConnectionSettings:
    endpoint: str
    database: str
    auth_mode: AuthMode
    ca_file: str | None
    static_user: str | None
    static_password: str | None
    sa_key_file: str | None
    access_token: str | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Find and group YDB tables that share the same schema structure."
    )
    parser.add_argument("--endpoint", required=True, help="YDB endpoint, e.g. grpcs://host:2135")
    parser.add_argument("--database", required=True, help="YDB database path")
    parser.add_argument(
        "--start-path",
        default=".",
        help="Path inside database to scan recursively (default: .)",
    )
    parser.add_argument(
        "--auth-mode",
        choices=("none", "env", "static", "metadata", "sakey", "token"),
        default="env",
        help="Authentication mode (default: env)",
    )
    parser.add_argument("--ca-file", help="Optional custom CA certificate path (PEM)")
    parser.add_argument("--static-user", help="Static auth username (for --auth-mode static)")
    parser.add_argument("--static-password", help="Static auth password (for --auth-mode static)")
    parser.add_argument("--sa-key-file", help="Service account key file (for --auth-mode sakey)")
    parser.add_argument("--access-token", help="Access token (for --auth-mode token)")
    parser.add_argument(
        "--wait-timeout",
        type=float,
        default=10.0,
        help="Driver wait timeout in seconds (default: 10)",
    )
    parser.add_argument(
        "--skip-describe-errors",
        action="store_true",
        help="Skip tables that fail schema describe, otherwise fail fast",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args()


def load_optional_ca(ca_file: str | None) -> bytes | None:
    if not ca_file:
        return None
    return Path(ca_file).read_bytes()


def build_credentials(settings: ConnectionSettings, ca_data: bytes | None):
    if settings.auth_mode == "none":
        return ydb.AnonymousCredentials()

    if settings.auth_mode == "env":
        return ydb.credentials_from_env_variables()

    if settings.auth_mode == "metadata":
        return ydb.iam.MetadataUrlCredentials()

    if settings.auth_mode == "sakey":
        if not settings.sa_key_file:
            raise ValueError("--sa-key-file is required for --auth-mode sakey")
        return ydb.iam.ServiceAccountCredentials.from_file(key_file=settings.sa_key_file)

    if settings.auth_mode == "token":
        if not settings.access_token:
            raise ValueError("--access-token is required for --auth-mode token")
        return ydb.AccessTokenCredentials(settings.access_token)

    if settings.auth_mode == "static":
        if not settings.static_user or settings.static_password is None:
            raise ValueError("--static-user and --static-password are required for --auth-mode static")
        driver_config = ydb.get_config(
            endpoint=settings.endpoint,
            database=settings.database,
            root_certificates=ca_data,
        )
        return ydb.StaticCredentials(
            driver_config=driver_config,
            user=settings.static_user,
            password=settings.static_password,
        )

    raise ValueError(f"Unsupported auth mode: {settings.auth_mode}")


def join_path(parent: str, name: str) -> str:
    if parent in ("", "."):
        return name
    return f"{parent.rstrip('/')}/{name}"


def list_tables_recursive(driver: ydb.Driver, start_path: str) -> List[str]:
    found: List[str] = []
    pending = [start_path]
    while pending:
        current = pending.pop()
        directory = driver.scheme_client.list_directory(current)
        for child in directory.children:
            child_path = join_path(current, child.name)
            if child.is_directory_or_database():
                pending.append(child_path)
                continue
            if child.is_any_table():
                found.append(child_path)
    found.sort()
    return found


def serialize_type(column: ydb.Column) -> str:
    type_pb = column.type_pb
    if hasattr(type_pb, "SerializeToString"):
        raw = type_pb.SerializeToString(deterministic=True)
        return raw.hex()
    return str(type_pb)


def index_kind(index: ydb.TableIndex) -> str:
    pb = index.to_pb()
    # Oneof name for index kind in YDB proto.
    kind = pb.WhichOneof("type")
    return kind or "unknown"


def schema_fingerprint(desc: ydb.TableDescription) -> SchemaFingerprint:
    type_by_col_name: Dict[str, str] = {column.name: serialize_type(column) for column in desc.columns}
    all_column_types = sorted(type_by_col_name.values())
    primary_key_types = tuple(type_by_col_name.get(col_name, "<unknown>") for col_name in desc.primary_key)

    index_signatures: List[Tuple[str, Tuple[str, ...], Tuple[str, ...]]] = []
    for index in desc.indexes:
        index_col_types = tuple(type_by_col_name.get(col_name, "<unknown>") for col_name in index.index_columns)
        data_col_types = tuple(type_by_col_name.get(col_name, "<unknown>") for col_name in index.data_columns)
        index_signatures.append((index_kind(index), index_col_types, data_col_types))
    index_signatures.sort()

    return (
        len(desc.columns),
        tuple(all_column_types),
        len(desc.primary_key),
        primary_key_types,
        tuple(index_signatures),
    )


def describe_table(pool: ydb.SessionPool, table_path: str) -> ydb.TableDescription:
    def callee(session: ydb.Session):
        return session.describe_table(table_path)

    return pool.retry_operation_sync(callee)


def group_tables_by_schema(
    pool: ydb.SessionPool, table_paths: Iterable[str], skip_describe_errors: bool
) -> Dict[SchemaFingerprint, List[str]]:
    groups: Dict[SchemaFingerprint, List[str]] = defaultdict(list)
    for table_path in table_paths:
        try:
            desc = describe_table(pool, table_path)
        except Exception:
            if skip_describe_errors:
                logging.exception("Failed to describe table %s, skipping", table_path)
                continue
            raise
        key = schema_fingerprint(desc)
        groups[key].append(table_path)

    return groups


def print_result(groups: Dict[SchemaFingerprint, List[str]]) -> None:
    non_trivial_groups = [sorted(items) for items in groups.values() if len(items) > 1]
    non_trivial_groups.sort(key=lambda group: (len(group), group))

    if not non_trivial_groups:
        print("No groups with similar structure (size > 1) were found.")
        return

    print("Groups of tables with the same schema structure:\n")
    for idx, group in enumerate(non_trivial_groups, start=1):
        print(f"Group {idx} ({len(group)} tables):")
        for table_name in group:
            print(f"  - {table_name}")
        print()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    logging.getLogger("ydb").setLevel(logging.WARNING)

    settings = ConnectionSettings(
        endpoint=args.endpoint,
        database=args.database,
        auth_mode=args.auth_mode,
        ca_file=args.ca_file,
        static_user=args.static_user,
        static_password=args.static_password,
        sa_key_file=args.sa_key_file,
        access_token=args.access_token,
    )

    ca_data = load_optional_ca(settings.ca_file)
    credentials = build_credentials(settings, ca_data)
    with ydb.Driver(
        endpoint=settings.endpoint,
        database=settings.database,
        credentials=credentials,
        root_certificates=ca_data,
    ) as driver:
        driver.wait(timeout=args.wait_timeout, fail_fast=True)
        table_paths = list_tables_recursive(driver, args.start_path)
        logging.info("Found %d table(s) under path %s", len(table_paths), args.start_path)
        with ydb.SessionPool(driver) as pool:
            groups = group_tables_by_schema(pool, table_paths, args.skip_describe_errors)
    print_result(groups)


if __name__ == "__main__":
    main()
