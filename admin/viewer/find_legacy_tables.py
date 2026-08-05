#!/usr/bin/env python3
"""Find tables created in legacy mode via Embedded UI viewer API.

Walks the scheme tree with /scheme/directory (non-recursive) and checks each
TABLE via /viewer/json/describe?partition_config=true.

A table is considered legacy when PathDescription.Table.PartitionConfig has:
  * no ColumnFamilies entry with Id: 0, or
  * family 0 without StorageConfig

Auth: --auth Login (or OAuth) and token from ~/.ydb/token.
Does not auto-refresh the token (use get_token.py separately if needed).
"""

import os
import sys
import time
import requests
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from multiprocessing.pool import ThreadPool
from urllib.parse import quote

VIEWER_URL_BASE = ''
VIEWER_HEADERS = {}

URL_SCHEME_DIRECTORY = '{url_base}/scheme/directory?database={database}&path={path}'
URL_DESCRIBE = '{url_base}/viewer/json/describe?path={path}&partition_config=true'

HTTP_TIMEOUT = 60
DIRECTORY_TYPES = frozenset({'DIRECTORY', 'DATABASE'})
TABLE_TYPE = 'TABLE'


def log(msg, file=sys.stderr):
    print(f'[{time.ctime()}] {msg}', file=file, flush=True)


def setup_auth(auth_mode):
    global VIEWER_HEADERS
    if auth_mode == '' or auth_mode.lower() == 'disabled':
        VIEWER_HEADERS = {}
        return

    token_path = os.path.expanduser('~/.ydb/token')
    if not os.path.isfile(token_path):
        print(f'{token_path} does not exist', file=sys.stderr)
        sys.exit(1)

    token = open(token_path).read().strip()
    if not token:
        print(f'{token_path} is empty', file=sys.stderr)
        sys.exit(1)

    VIEWER_HEADERS = {
        'Authorization': f'{auth_mode} {token}',
    }


def load_json(url):
    response = requests.get(
        url, headers=VIEWER_HEADERS, verify=False, timeout=HTTP_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def join_path(parent, name):
    return f'{parent.rstrip("/")}/{name}'


def list_directory(database, path):
    url = URL_SCHEME_DIRECTORY.format(
        url_base=VIEWER_URL_BASE,
        database=quote(database, safe='/'),
        path=quote(path, safe='/'),
    )
    return load_json(url)


def collect_tables(database, start_path, include_sys=False):
    """BFS over scheme directories; return sorted list of TABLE paths."""
    tables = []
    queue = [start_path]
    seen_dirs = set()

    while queue:
        path = queue.pop(0)
        if path in seen_dirs:
            continue
        seen_dirs.add(path)

        try:
            data = list_directory(database, path)
        except Exception as exc:
            log(f'ERROR listing {path}: {exc}')
            continue

        children = data.get('children') or []
        log(f'Listed {path}: {len(children)} child(ren)')

        for child in children:
            name = child.get('name')
            if not name:
                continue
            child_type = child.get('type')
            child_path = join_path(path, name)

            if child_type in DIRECTORY_TYPES:
                if not include_sys and name.startswith('.'):
                    continue
                queue.append(child_path)
            elif child_type == TABLE_TYPE:
                tables.append(child_path)

    tables.sort()
    return tables


def legacy_reason(describe):
    """Return reason string if table is legacy, else None."""
    table = (describe.get('PathDescription') or {}).get('Table')
    if not table:
        return 'no PathDescription.Table'

    partition_config = table.get('PartitionConfig') or {}
    families = partition_config.get('ColumnFamilies') or []

    family0 = None
    for family in families:
        if family.get('Id') == 0:
            family0 = family
            break

    if family0 is None:
        return 'no ColumnFamilies entry with Id: 0'

    if 'StorageConfig' not in family0 or not family0.get('StorageConfig'):
        return 'family 0 has no StorageConfig'

    return None


def check_table(path):
    url = URL_DESCRIBE.format(
        url_base=VIEWER_URL_BASE,
        path=quote(path, safe='/'),
    )
    try:
        describe = load_json(url)
    except Exception as exc:
        return path, f'ERROR: {exc}', True

    reason = legacy_reason(describe)
    if reason is None:
        return path, None, False
    return path, reason, False


def main():
    parser = ArgumentParser(
        formatter_class=RawDescriptionHelpFormatter,
        description=__doc__,
        epilog='''\
Examples:
  %(prog)s --viewer-url https://somehost:8765 \\
      --auth Login /Root/database

  %(prog)s --viewer-url https://somehost:8765 --auth Login \\
      --path /Root/database/schema1 /Root/database
''',
    )
    parser.add_argument('--viewer-url', required=True)
    parser.add_argument('--auth', dest='auth_mode', default='Login')  # OAuth or Login
    parser.add_argument(
        'database',
        help='Database path used for /scheme/directory (e.g. /Root/database)',
    )
    parser.add_argument(
        '--path',
        default=None,
        help='Start directory for the walk (default: same as database)',
    )
    parser.add_argument(
        '--include-sys',
        action='store_true',
        help='Also walk directories whose names start with "." (e.g. .sys)',
    )
    parser.add_argument(
        '--threads',
        type=int,
        default=8,
        help='Parallel describe requests (default: 8)',
    )
    parser.add_argument(
        '--show-ok',
        action='store_true',
        help='Also print non-legacy tables to stderr',
    )
    args = parser.parse_args()

    if args.threads < 1:
        parser.error('--threads must be >= 1')

    setup_auth(args.auth_mode)

    global VIEWER_URL_BASE
    VIEWER_URL_BASE = args.viewer_url.rstrip('/')

    database = args.database
    start_path = args.path or database

    log(f'Scanning database={database} path={start_path}')
    tables = collect_tables(database, start_path, include_sys=args.include_sys)
    log(f'Found {len(tables)} table(s), checking PartitionConfig...')

    legacy_count = 0
    error_count = 0

    with ThreadPool(min(args.threads, len(tables) or 1)) as pool:
        for index, (path, reason, is_error) in enumerate(
            pool.imap(check_table, tables), start=1,
        ):
            if is_error:
                error_count += 1
                log(f'[{index}/{len(tables)}] {path}: {reason}')
                continue
            if reason is None:
                if args.show_ok:
                    log(f'[{index}/{len(tables)}] OK {path}')
                continue

            legacy_count += 1
            # stdout: path + reason for easy piping / review
            print(f'{path}\t{reason}', flush=True)
            log(f'[{index}/{len(tables)}] LEGACY {path}: {reason}')

    log(
        f'Done: tables={len(tables)}, legacy={legacy_count}, '
        f'errors={error_count}'
    )
    if error_count:
        sys.exit(2)


if __name__ == '__main__':
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    main()
