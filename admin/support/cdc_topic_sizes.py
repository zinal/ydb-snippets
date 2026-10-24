#!/usr/bin/env python3
"""CSV: source table, its storage without secondary indexes, CDC topic storage.

Connection string, either form:

    export YDB_CONNECTION_STRING='grpcs://localhost:2135/Root/source'
    export YDB_CONNECTION_STRING='grpcs://localhost:2135/?database=/Root/source'

    export YDB_SSL_ROOT_CERTIFICATES_FILE='~/Work/Replicad/CA/certs/ca.crt'
    export YDB_TOKEN=`ydb auth get-token -f`

    python3 cdc_topic_sizes.py > cdc_sizes.csv

stdout is only the CSV. Errors go to stderr. A metric that could not be
collected is -1.

storage_bytes is DescribeTable(include_table_stats).table_stats.store_size
minus each index.size_bytes. store_size is the table data, the table LSM
index, and every scheme index. index.size_bytes is the same DataSize that
was added for that index, so the difference is the table alone.

cdc_bytes is the sum of DescribeTopic(include_stats).topic_stats.store_size_bytes
for every changefeed of the table. If any feed fails, the cell is -1.
"""

import argparse
import csv
import os
import sys
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

import ydb


_PRINT_LOCK = threading.Lock()


def log_error(text):
    with _PRINT_LOCK:
        print(text, file=sys.stderr)


def join_path(parent, name):
    return parent.rstrip("/") + "/" + name


def relative_table(database, path):
    prefix = database.rstrip("/") + "/"
    if path.startswith(prefix):
        return path[len(prefix):]
    return path


def parse_connection_string(connection_string):
    """Return (endpoint, database) for both YDB connection string shapes.

    grpcs://host:2135/?database=/Root/source
    grpcs://host:2135/Root/source
    """
    raw = connection_string.strip()
    if "://" not in raw:
        raw = "grpcs://" + raw

    parsed = urllib.parse.urlparse(raw)
    if parsed.scheme not in ("grpc", "grpcs") or not parsed.netloc:
        raise ValueError(
            "connection string must look like grpcs://host:2135/Root/source "
            "or grpcs://host:2135/?database=/Root/source, got %r" % connection_string
        )

    database = None
    if parsed.query:
        values = urllib.parse.parse_qs(parsed.query).get("database") or []
        if values and values[0]:
            database = values[0]

    if not database:
        path = urllib.parse.unquote(parsed.path or "").rstrip("/")
        if path and path != "/":
            database = path

    if not database:
        raise ValueError(
            "connection string has no database path, got %r" % connection_string
        )
    if not database.startswith("/"):
        database = "/" + database

    return "%s://%s" % (parsed.scheme, parsed.netloc), database


def load_root_certificates():
    """PEM bytes for DriverConfig.root_certificates.

    The SDK does not apply YDB_SSL_ROOT_CERTIFICATES_FILE on its own. Without
    these bytes gRPC trusts only the default public roots and rejects a
    private CA.
    """
    path = os.getenv("YDB_SSL_ROOT_CERTIFICATES_FILE")
    if not path:
        return None
    try:
        with open(path, "rb") as certificate_file:
            data = certificate_file.read()
    except OSError as exc:
        raise RuntimeError(
            "cannot read YDB_SSL_ROOT_CERTIFICATES_FILE %s: %s" % (path, exc)
        ) from exc
    if not data:
        raise RuntimeError("YDB_SSL_ROOT_CERTIFICATES_FILE is empty: %s" % path)
    return data


def make_credentials():
    token = os.getenv("YDB_TOKEN")
    if token:
        for name in ("AuthTokenCredentials", "AccessTokenCredentials"):
            credentials_cls = getattr(ydb, name, None)
            if credentials_cls is not None:
                return credentials_cls(token)
        raise RuntimeError("YDB_TOKEN is set, but this ydb SDK cannot build token credentials")

    watched = (
        "YDB_ACCESS_TOKEN_CREDENTIALS",
        "YDB_SERVICE_ACCOUNT_KEY_FILE_CREDENTIALS",
        "YDB_METADATA_CREDENTIALS",
        "YDB_USER",
        "YDB_ANONYMOUS_CREDENTIALS",
        "YDB_OAUTH2_KEY_FILE",
    )
    if any(os.getenv(name) for name in watched):
        return ydb.credentials_from_env_variables()
    return None


def make_driver(args):
    credentials = make_credentials()
    kwargs = {}
    if credentials is not None:
        kwargs["credentials"] = credentials
    root_certificates = load_root_certificates()
    if root_certificates is not None:
        kwargs["root_certificates"] = root_certificates

    if args.connection_string:
        endpoint, database = parse_connection_string(args.connection_string)
    else:
        endpoint, database = args.endpoint, args.database

    config = ydb.DriverConfig(endpoint, database, **kwargs)
    driver = ydb.Driver(config)
    driver.wait(fail_fast=True, timeout=args.timeout)
    return driver, database


def list_row_tables(scheme, root):
    tables = []
    stack = [root]
    while stack:
        path = stack.pop()
        listing = scheme.list_directory(path)
        for child in listing.children:
            if child.name.startswith("."):
                continue
            child_path = join_path(path, child.name)
            if child.is_directory():
                stack.append(child_path)
            elif child.is_row_table():
                tables.append(child_path)
    tables.sort()
    return tables


def wrap_describe_table(_rpc_state, response_pb, _session_state):
    ydb.issues._process_response(response_pb.operation)
    message = ydb._apis.ydb_table.DescribeTableResult()
    response_pb.operation.result.Unpack(message)
    return message


class TableDescriber(object):
    def __init__(self, driver):
        self._driver = driver
        self._local = threading.local()
        self._settings = ydb.DescribeTableSettings().with_include_table_stats(True)

    def _session(self):
        session = getattr(self._local, "session", None)
        if session is None:
            session = self._driver.table_client.session().create()
            self._local.session = session
        return session

    def _reset_session(self):
        session = getattr(self._local, "session", None)
        if session is not None:
            try:
                session.delete()
            except ydb.Error:
                pass
        self._local.session = None

    def describe(self, path):
        delay = 0.2
        last_error = None
        for _attempt in range(5):
            session = self._session()
            try:
                return session._driver(
                    ydb._session_impl.describe_table_request_factory(
                        session._state, path, self._settings),
                    ydb._apis.TableService.Stub,
                    ydb._apis.TableService.DescribeTable,
                    wrap_describe_table,
                    self._settings,
                    (session._state,),
                    session._state.endpoint,
                )
            except (ydb.issues.Overloaded, ydb.issues.Unavailable, ydb.issues.Aborted) as exc:
                last_error = exc
                time.sleep(delay)
                delay = min(delay * 2, 5)
            except ydb.issues.BadSession as exc:
                last_error = exc
                self._reset_session()
        raise last_error


def describe_topic(topic_client, path):
    delay = 0.2
    last_error = None
    for _attempt in range(5):
        try:
            return topic_client.describe_topic(path, include_stats=True)
        except (ydb.issues.Overloaded, ydb.issues.Unavailable, ydb.issues.Aborted) as exc:
            last_error = exc
            time.sleep(delay)
            delay = min(delay * 2, 5)
    raise last_error


def storage_without_secondary_indexes(description):
    if not description.HasField("table_stats"):
        raise RuntimeError("table stats were not returned")
    total = int(description.table_stats.store_size)
    indexes = sum(int(index.size_bytes) for index in description.indexes)
    if indexes > total:
        raise RuntimeError(
            "secondary index size %d is greater than table store_size %d" % (indexes, total))
    return total - indexes


def topic_store_size(description):
    stats = description.topic_stats
    if stats is None:
        raise RuntimeError("topic stats were not returned")
    return int(stats.store_size_bytes)


def collect(driver, root, workers):
    tables = list_row_tables(driver.scheme_client, root)
    describer = TableDescriber(driver)
    jobs = []
    for table_path in tables:
        try:
            description = describer.describe(table_path)
        except Exception as exc:
            log_error("ошибка: %s: не удалось описать таблицу: %s" % (table_path, exc))
            continue
        feeds = [feed.name for feed in description.changefeeds]
        if not feeds:
            continue
        try:
            storage_bytes = storage_without_secondary_indexes(description)
        except Exception as exc:
            log_error("ошибка: %s: не удалось получить объём таблицы: %s" % (table_path, exc))
            storage_bytes = -1
        jobs.append((table_path, storage_bytes, feeds))

    topic_client = driver.topic_client

    def load_feed(table_path, feed_name):
        topic_path = join_path(table_path, feed_name)
        try:
            return topic_store_size(describe_topic(topic_client, topic_path))
        except Exception as exc:
            log_error("ошибка: %s: не удалось получить объём CDC: %s" % (topic_path, exc))
            return None

    rows = []
    with ThreadPoolExecutor(max_workers=max(workers, 1)) as pool:
        future_map = {}
        for table_path, storage_bytes, feeds in jobs:
            futures = [pool.submit(load_feed, table_path, feed) for feed in feeds]
            future_map[table_path] = futures

        for table_path, storage_bytes, _feeds in jobs:
            sizes = [future.result() for future in future_map[table_path]]
            if any(size is None for size in sizes):
                cdc_bytes = -1
            else:
                cdc_bytes = sum(sizes)
            rows.append((table_path, storage_bytes, cdc_bytes))
    return rows


def main():
    parser = argparse.ArgumentParser(
        description="CSV of table storage and CDC storage by source table")
    parser.add_argument("--connection-string", default=os.getenv("YDB_CONNECTION_STRING"))
    parser.add_argument("--endpoint", default=os.getenv("YDB_ENDPOINT"))
    parser.add_argument("--database", default=os.getenv("YDB_DATABASE"))
    parser.add_argument("--root", help="Scheme path to scan. Default: the database root")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    if not args.connection_string and not (args.endpoint and args.database):
        parser.error("pass --connection-string or both --endpoint and --database")

    driver, database = make_driver(args)
    root = args.root or database
    if not root.startswith("/"):
        root = join_path(database, root)

    try:
        rows = collect(driver, root, args.workers)
    finally:
        driver.stop()

    rows.sort(key=lambda row: relative_table(database, row[0]))
    writer = csv.writer(sys.stdout, lineterminator="\n")
    writer.writerow(("table", "storage_bytes", "cdc_bytes"))
    for table_path, storage_bytes, cdc_bytes in rows:
        writer.writerow((relative_table(database, table_path), storage_bytes, cdc_bytes))

    if any(storage < 0 or cdc < 0 for _table, storage, cdc in rows):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

