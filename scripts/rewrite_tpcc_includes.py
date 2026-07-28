#!/usr/bin/env python3
"""Rewrite local includes to the new tpcc/util and tpcc/ layout."""

from pathlib import Path

ROOT = Path("/workspace")

UTIL_MAP = {
    "future.h": "tpcc/util/future.h",
    "spinlock.h": "tpcc/util/spinlock.h",
    "histogram.h": "tpcc/util/histogram.h",
    "thread_pool.h": "tpcc/util/thread_pool.h",
    "task_queue.h": "tpcc/util/task_queue.h",
    "timer_queue.h": "tpcc/util/timer_queue.h",
    "spsc_circular_queue.h": "tpcc/util/spsc_circular_queue.h",
    "log_backend.h": "tpcc/util/log_backend.h",
    "log.h": "tpcc/util/log.h",
    "coro_traits.h": "tpcc/util/coro_traits.h",
}

LIBRARY_MAP = {
    "constants.h": "tpcc/constants.h",
    "util.h": "tpcc/util.h",
    "terminal_stats.h": "tpcc/terminal_stats.h",
    "transaction_context.h": "tpcc/transaction_context.h",
    "runner_config.h": "tpcc/runner_config.h",
    "runner_display_data.h": "tpcc/runner_display_data.h",
}

CONTRIB_MAP = {
    "pg_session.h": "tpcc/postgres/pg_session.h",
    "pg_connection_pool.h": "tpcc/postgres/pg_connection_pool.h",
    "query_result.h": "tpcc/postgres/query_result.h",
    "common_queries.h": "tpcc/postgres/common_queries.h",
    "transactions.h": "tpcc/postgres/transactions.h",
    "terminal.h": "tpcc/postgres/terminal.h",
    "runner.h": "tpcc/postgres/runner.h",
    "init.h": "tpcc/postgres/init.h",
    "import.h": "tpcc/postgres/import.h",
    "clean.h": "tpcc/postgres/clean.h",
    "check.h": "tpcc/postgres/check.h",
    "path_checker.h": "tpcc/postgres/path_checker.h",
    "tui_base.h": "tpcc/postgres/tui_base.h",
    "runner_tui.h": "tpcc/postgres/runner_tui.h",
    "import_tui.h": "tpcc/postgres/import_tui.h",
    "import_display_data.h": "tpcc/postgres/import_display_data.h",
    "scroller.h": "tpcc/postgres/scroller.h",
    "logs_scroller.h": "tpcc/postgres/logs_scroller.h",
}

ALL_MAP = {**UTIL_MAP, **LIBRARY_MAP, **CONTRIB_MAP}

DIRS = [
    ROOT / "util/tpcc/include/tpcc/util",
    ROOT / "util/tpcc/src",
    ROOT / "library/tpcc/include/tpcc",
    ROOT / "library/tpcc/src",
    ROOT / "contrib/tpcc-postgres/src",
    ROOT / "contrib/tpcc-postgres/src/ut",
]


def rewrite_includes(text: str) -> str:
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith('#include "'):
            name = stripped.split('"')[1]
            if name in ALL_MAP:
                line = f'#include <{ALL_MAP[name]}>'
        lines.append(line)
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


for d in DIRS:
    if not d.exists():
        continue
    for path in d.rglob("*"):
        if path.suffix not in {".h", ".cpp"}:
            continue
        original = path.read_text()
        updated = rewrite_includes(original)
        if updated != original:
            path.write_text(updated)

print("Include rewrite complete")
