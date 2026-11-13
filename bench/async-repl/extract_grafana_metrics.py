#!/usr/bin/env python3
"""Суммарные метрики Grafana по окнам завершённого прогона Toster.

Читает каталог результатов (log-FORMAT-COMPRESSION.txt и FORMAT-COMPRESSION.txt)
и снимает те же суммы, что панели дашборда «YDB Aggregate load»:

  CPU, с     sum(increase(utils_ElapsedMicrosec{database=...}[окно])) / 1e6
  транзакции sum(increase(ydb_table_transaction_total_duration_milliseconds_count{...}[окно]))
  запись, MB sum(increase(ydb_topic_write_bytes{...}[окно])) / 1e6
  чтение, MB sum(increase(ydb_topic_read_bytes{...}[окно])) / 1e6

Окна берутся из логов прогона, импорт S3 в них не входит:

  initial_sync  от «ожидание начальной синхронизации»
                до «начальная синхронизация завершена»
  workload      от run_started до run_finished
                (init-pause перед нагрузкой в окно не входит)

Для FORMAT=NONE фазы initial_sync нет. CSV пишется только если все запросы успешны.

Пример после ./round.sh:

  python3 extract_grafana_metrics.py \\
    --url http://gw1:3000 --user admin --password "$GRAFANA_PASSWORD" \\
    --logs results --output results/grafana-metrics.csv
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

FORMATS = ("BINARY", "JSON", "NONE")
COMPRESSIONS = ("NONE", "ZSTD")

ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
SYNC_START_RE = re.compile(
    r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z) ожидание начальной синхронизации"
)
SYNC_END_RE = re.compile(
    r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z) начальная синхронизация завершена"
)
SKIP_REPLICATION_RE = re.compile(r"Пропускаем создания репликации")
DB_RE = re.compile(r"(/[^/\s\"]+/db\d+)")
RESULT_LINE_RE = re.compile(
    r"elapsed_s=([\d.]+) tx_per_s=([\d.]+) errors_per_s=([\d.]+) tx=(\d+) errors=(\d+)"
)

# Имена колонок CSV и соответствующие поля фазы.
COLUMNS = [
    "format",
    "compression",
    "phase",
    "window_start",
    "window_end",
    "duration_s",
    "source_database",
    "target_database",
    "cpu_source_s",
    "cpu_target_s",
    "transactions_source",
    "transactions_target",
    "topic_write_source_mb",
    "topic_read_source_mb",
    "topic_write_target_mb",
    "topic_read_target_mb",
    "client_transactions",
    "client_errors",
]

# Метрика -> шаблон PromQL. {db} и {dur} подставляются на каждое окно.
PROMQL = {
    "cpu_s": 'sum(increase(utils_ElapsedMicrosec{{database="{db}"}}[{dur}s])) / 1000000',
    "transactions": (
        "sum(increase(ydb_table_transaction_total_duration_milliseconds_count"
        '{{database="{db}"}}[{dur}s]))'
    ),
    "topic_write_mb": 'sum(increase(ydb_topic_write_bytes{{database="{db}"}}[{dur}s])) / 1000000',
    "topic_read_mb": 'sum(increase(ydb_topic_read_bytes{{database="{db}"}}[{dur}s])) / 1000000',
}

METRIC_FIELDS = (
    ("cpu_s", "source", "cpu_source_s"),
    ("cpu_s", "target", "cpu_target_s"),
    ("transactions", "source", "transactions_source"),
    ("transactions", "target", "transactions_target"),
    ("topic_write_mb", "source", "topic_write_source_mb"),
    ("topic_read_mb", "source", "topic_read_source_mb"),
    ("topic_write_mb", "target", "topic_write_target_mb"),
    ("topic_read_mb", "target", "topic_read_target_mb"),
)


@dataclass(frozen=True)
class Window:
    format: str
    compression: str
    phase: str
    start: datetime
    end: datetime
    client_transactions: int | None = None
    client_errors: int | None = None

    @property
    def duration_s(self) -> int:
        seconds = int((self.end - self.start).total_seconds())
        if seconds <= 0:
            raise ValueError(
                f"{self.format}/{self.compression} {self.phase}: "
                f"пустое окно {self.start.isoformat()} .. {self.end.isoformat()}"
            )
        return seconds


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def parse_time(value: str) -> datetime:
    if value.endswith("Z"):
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError(f"у метки времени нет часового пояса: {value}")
    return parsed.astimezone(timezone.utc)


def iso_z(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def most_common(values: list[str]) -> str | None:
    if not values:
        return None
    return Counter(values).most_common(1)[0][0]


def detect_databases(log_dir: Path) -> tuple[str | None, str | None]:
    """Источник — пути из stats-*.txt (preload на db1), приёмник — пути репликации в log-*.txt."""
    source_hits: list[str] = []
    target_hits: list[str] = []
    for path in sorted(log_dir.glob("stats-*.txt")):
        text = path.read_text(errors="replace")
        source_hits.extend(DB_RE.findall(text))
    for path in sorted(log_dir.glob("log-*.txt")):
        with path.open(errors="replace") as handle:
            for line in handle:
                if "/replication/" not in line and "source_repl" not in line:
                    continue
                target_hits.extend(DB_RE.findall(strip_ansi(line)))
    return most_common(source_hits), most_common(target_hits)


def parse_result_file(path: Path) -> tuple[datetime, datetime, int, int]:
    run_started = None
    run_finished = None
    client_tx = None
    client_errors = None
    with path.open(errors="replace") as handle:
        for raw in handle:
            line = raw.strip()
            if line.startswith("run_started="):
                run_started = parse_time(line.split("=", 1)[1])
            elif line.startswith("run_finished="):
                run_finished = parse_time(line.split("=", 1)[1])
            else:
                match = RESULT_LINE_RE.search(line)
                if match:
                    client_tx = int(match.group(4))
                    client_errors = int(match.group(5))
    if run_started is None or run_finished is None or client_tx is None or client_errors is None:
        raise ValueError(f"{path.name}: нет run_started, run_finished или итоговой строки tx=")
    return run_started, run_finished, client_tx, client_errors


def parse_sync_window(path: Path) -> tuple[datetime | None, datetime | None, bool]:
    start = None
    end = None
    skipped = False
    with path.open(errors="replace") as handle:
        for raw in handle:
            line = strip_ansi(raw)
            if SKIP_REPLICATION_RE.search(line):
                skipped = True
            match = SYNC_START_RE.search(line)
            if match:
                start = parse_time(match.group(1))
            match = SYNC_END_RE.search(line)
            if match:
                end = parse_time(match.group(1))
    return start, end, skipped


def discover_runs(log_dir: Path) -> list[Window]:
    if not log_dir.is_dir():
        raise ValueError(f"каталог логов не найден: {log_dir}")
    windows: list[Window] = []
    found = False
    for fmt in FORMATS:
        for compression in COMPRESSIONS:
            if fmt == "NONE" and compression != "NONE":
                continue
            result_path = log_dir / f"{fmt}-{compression}.txt"
            log_path = log_dir / f"log-{fmt}-{compression}.txt"
            if not result_path.exists() and not log_path.exists():
                continue
            found = True
            if not result_path.exists() or not log_path.exists():
                raise ValueError(
                    f"неполная пара для {fmt}/{compression}: "
                    f"{result_path.name} и {log_path.name} должны быть оба"
                )
            run_started, run_finished, client_tx, client_errors = parse_result_file(result_path)
            sync_start, sync_end, skipped = parse_sync_window(log_path)
            if fmt == "NONE":
                if sync_start or sync_end:
                    raise ValueError(f"{log_path.name}: для NONE не ожидается окно синхронизации")
            elif skipped or sync_start is None or sync_end is None:
                raise ValueError(
                    f"{log_path.name}: нет границ начальной синхронизации "
                    "(ожидание / завершена). Импорт S3 в окно не берётся."
                )
            else:
                windows.append(
                    Window(fmt, compression, "initial_sync", sync_start, sync_end)
                )
            windows.append(
                Window(
                    fmt,
                    compression,
                    "workload",
                    run_started,
                    run_finished,
                    client_tx,
                    client_errors,
                )
            )
    if not found:
        raise ValueError(
            f"в {log_dir} нет пар FORMAT-COMPRESSION.txt и log-FORMAT-COMPRESSION.txt"
        )
    windows.sort(key=lambda item: (item.start, item.phase))
    return windows


class GrafanaClient:
    def __init__(self, base_url: str, user: str | None, password: str | None,
                 token: str | None, datasource: str, timeout: float, insecure: bool):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.insecure = insecure
        self.headers = {"Accept": "application/json"}
        if token:
            self.headers["Authorization"] = f"Bearer {token}"
        elif user is not None and password is not None:
            token_bytes = f"{user}:{password}".encode()
            self.headers["Authorization"] = "Basic " + base64.b64encode(token_bytes).decode()
        else:
            raise ValueError("нужны --user и --password либо --token")
        self.datasource_uid = self._resolve_datasource(datasource)

    def _ssl_context(self) -> ssl.SSLContext:
        if self.insecure:
            return ssl._create_unverified_context()
        return ssl.create_default_context()

    def _request(self, path: str) -> dict:
        request = urllib.request.Request(self.base_url + path, headers=self.headers)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout, context=self._ssl_context()) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as error:
            body = error.read().decode(errors="replace")[:500]
            raise RuntimeError(f"Grafana {error.code} {path}: {body}") from error
        except urllib.error.URLError as error:
            raise RuntimeError(f"Grafana недоступна ({self.base_url}): {error.reason}") from error

    def _resolve_datasource(self, name: str) -> str:
        payload = self._request("/api/datasources")
        if not isinstance(payload, list):
            raise RuntimeError("неожиданный ответ /api/datasources")
        prometheus = [item for item in payload if item.get("type") == "prometheus"]
        chosen = next((item for item in prometheus if item.get("name") == name), None)
        if chosen is None and name == "prometheus":
            chosen = next((item for item in prometheus if item.get("isDefault")), None)
            if chosen is None and len(prometheus) == 1:
                chosen = prometheus[0]
        if chosen is None:
            names = ", ".join(item.get("name", "?") for item in prometheus) or "нет"
            raise RuntimeError(f"Prometheus datasource {name!r} не найден. Доступны: {names}")
        uid = chosen.get("uid")
        if not uid:
            raise RuntimeError(f"у datasource {chosen.get('name')} нет uid")
        return uid

    def increase(self, promql: str, end: datetime) -> float:
        query = urllib.parse.urlencode({"query": promql, "time": f"{int(end.timestamp())}"})
        path = f"/api/datasources/proxy/uid/{self.datasource_uid}/api/v1/query?{query}"
        payload = self._request(path)
        if payload.get("status") != "success":
            raise RuntimeError(payload.get("error") or "prometheus query failed")
        result = payload.get("data", {}).get("result", [])
        if not result:
            return 0.0
        total = 0.0
        for series in result:
            value = float(series["value"][1])
            if value != value:  # NaN
                raise RuntimeError(f"NaN в ответе Prometheus: {promql}")
            total += value
        return total


def collect(client: GrafanaClient, windows: list[Window], source_db: str, target_db: str,
            workers: int) -> list[dict[str, str]]:
    databases = {"source": source_db, "target": target_db}
    jobs: list[tuple[int, str, str]] = []
    for index, window in enumerate(windows):
        for metric, side, _field in METRIC_FIELDS:
            promql = PROMQL[metric].format(db=databases[side], dur=window.duration_s)
            jobs.append((index, f"{metric}:{side}", promql))

    values: dict[tuple[int, str], float] = {}

    def run(job: tuple[int, str, str]) -> tuple[int, str, float]:
        index, key, promql = job
        return index, key, client.increase(promql, windows[index].end)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run, job) for job in jobs]
        for future in as_completed(futures):
            index, key, value = future.result()
            values[(index, key)] = value

    rows: list[dict[str, str]] = []
    for index, window in enumerate(windows):
        row = {
            "format": window.format,
            "compression": window.compression,
            "phase": window.phase,
            "window_start": iso_z(window.start),
            "window_end": iso_z(window.end),
            "duration_s": str(window.duration_s),
            "source_database": source_db,
            "target_database": target_db,
            "client_transactions": "" if window.client_transactions is None else str(window.client_transactions),
            "client_errors": "" if window.client_errors is None else str(window.client_errors),
        }
        for metric, side, field in METRIC_FIELDS:
            row[field] = f"{values[(index, f'{metric}:{side}')]:.2f}"
        rows.append(row)
    return rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def print_windows(windows: list[Window], source_db: str, target_db: str) -> None:
    print(f"source={source_db} target={target_db}")
    for window in windows:
        client = ""
        if window.client_transactions is not None:
            client = f" client_tx={window.client_transactions} client_errors={window.client_errors}"
        print(
            f"{window.format:6} {window.compression:4} {window.phase:13} "
            f"{iso_z(window.start)} .. {iso_z(window.end)} {window.duration_s:5}s{client}"
        )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Снять суммарные метрики Grafana по окнам каталога результатов Toster и записать CSV."
    )
    parser.add_argument("--url", default=os.environ.get("GRAFANA_URL"),
                        help="базовый URL Grafana, например http://gw1:3000 (или GRAFANA_URL)")
    parser.add_argument("--user", default=os.environ.get("GRAFANA_USER"),
                        help="пользователь basic auth (или GRAFANA_USER)")
    parser.add_argument("--password", default=os.environ.get("GRAFANA_PASSWORD"),
                        help="пароль basic auth (или GRAFANA_PASSWORD)")
    parser.add_argument("--token", default=os.environ.get("GRAFANA_TOKEN"),
                        help="API-токен вместо basic auth (или GRAFANA_TOKEN)")
    parser.add_argument("--logs", required=True, type=Path,
                        help="каталог с log-*-*.txt и *-*.txt после успешного прогона")
    parser.add_argument("--output", type=Path,
                        help="куда писать CSV (по умолчанию <logs>/grafana-metrics.csv)")
    parser.add_argument("--source-db", help="база-источник, метка database. По умолчанию из stats-*.txt")
    parser.add_argument("--target-db", help="база-приёмник, метка database. По умолчанию из log-*.txt")
    parser.add_argument("--datasource", default="prometheus",
                        help="имя Prometheus datasource в Grafana (по умолчанию prometheus)")
    parser.add_argument("--timeout", type=float, default=120.0, help="таймаут одного запроса, секунды")
    parser.add_argument("--workers", type=int, default=4, help="параллельных запросов к Grafana")
    parser.add_argument("--insecure", action="store_true", help="не проверять TLS-сертификат")
    parser.add_argument("--dry-run", action="store_true",
                        help="только разобрать окна и базы, в Grafana не ходить и CSV не писать")
    args = parser.parse_args(argv)
    if args.output is None:
        args.output = args.logs / "grafana-metrics.csv"
    if args.workers < 1:
        parser.error("--workers должен быть >= 1")
    if not args.dry_run and not args.url:
        parser.error("нужен --url или GRAFANA_URL")
    if not args.dry_run and not args.token and (not args.user or args.password is None):
        parser.error("нужны --user и --password либо --token")
    return args


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        windows = discover_runs(args.logs)
        detected_source, detected_target = detect_databases(args.logs)
    except ValueError as error:
        print(f"ошибка: {error}", file=sys.stderr)
        return 1
    source_db = args.source_db or detected_source
    target_db = args.target_db or detected_target
    if not source_db or not target_db:
        print(
            "ошибка: не удалось определить базы. Передайте --source-db и --target-db "
            f"(найдено source={detected_source!r} target={detected_target!r})",
            file=sys.stderr,
        )
        return 1
    if source_db == target_db:
        print(f"ошибка: источник и приёмник совпадают ({source_db})", file=sys.stderr)
        return 1
    if args.dry_run:
        print_windows(windows, source_db, target_db)
        return 0
    try:
        client = GrafanaClient(
            args.url, args.user, args.password, args.token,
            args.datasource, args.timeout, args.insecure,
        )
        rows = collect(client, windows, source_db, target_db, args.workers)
    except (RuntimeError, urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
        print(f"ошибка: {error}", file=sys.stderr)
        return 1
    write_csv(args.output, rows)
    print(f"записано {len(rows)} строк в {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
