"""Shared YDB connection helpers for uuid-sharded benchmarks."""

from __future__ import annotations

import os

import ydb


def connect_driver() -> ydb.Driver:
    endpoint = os.getenv("YDB_ENDPOINT")
    database = os.getenv("YDB_DATABASE")
    if not endpoint:
        raise RuntimeError("Set YDB_ENDPOINT")
    if not database:
        raise RuntimeError("Set YDB_DATABASE")

    root_certificates = ydb.load_ydb_root_certificate()
    credentials = ydb.credentials_from_env_variables()
    username = os.getenv("YDB_USER")
    password = os.getenv("YDB_PASSWORD")
    if username:
        driver_config = ydb.get_config(
            endpoint=endpoint,
            database=database,
            root_certificates=root_certificates,
        )
        credentials = ydb.StaticCredentials(driver_config, user=username, password=password)

    driver = ydb.Driver(
        endpoint=endpoint,
        database=database,
        root_certificates=root_certificates,
        credentials=credentials,
    )
    driver.wait(timeout=10, fail_fast=True)
    return driver


def table_path(table_name: str) -> str:
    database = os.getenv("YDB_DATABASE", "")
    if table_name.startswith("/"):
        return table_name
    if database.endswith("/"):
        return f"{database}{table_name}"
    return f"{database}/{table_name}"


def table_describe_paths(table_name: str) -> list[str]:
    """Candidate paths for scheme/describe APIs (relative and absolute)."""
    paths: list[str] = []
    for candidate in (table_name, table_path(table_name)):
        if candidate and candidate not in paths:
            paths.append(candidate)
    return paths
