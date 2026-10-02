#!/usr/bin/env python3
"""List unfinished SchemeShard transactions and the scheme objects they touch.

SchemeShard keeps running scheme transactions in ``TxInFlight``. The Embedded
UI exposes that list as HTML on the SchemeShard tablet page
``/tablets/app?TabletID=<schemeshard>&Page=TxList``. Each row is one
in-flight sub-operation. ``Page=TxInfo`` names the path ids SchemeShard stored
on that transaction, and ``Page=PathInfo`` turns a path id into a scheme path.

A transaction records up to three objects: the object being modified
(``target``), the source object (``source``), and a CDC stream (``cdc``).
An unset path id is omitted. One sub-operation produces one output row per
recorded path.

The SchemeShard id comes from a single database describe
(``ProcessingParams.SchemeShard``). A dropped or failed connection while
reading the transaction list, a transaction, or a path is retried. Access
denied is not retried. These tablet pages need DevUI monitoring access.

Auth: ``--auth Login`` (or OAuth) and a token in ``~/.ydb/token``.
"""

import os
import re
import sys
import threading
import time
import requests
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from html import unescape
from html.parser import HTMLParser
from multiprocessing.pool import ThreadPool
from urllib.parse import parse_qs, quote

VIEWER_URL_BASE = ''
VIEWER_HEADERS = {}

URL_DESCRIBE = '{url_base}/viewer/json/describe?{query}'
URL_TABLET_APP = '{url_base}/tablets/app'

HTTP_TIMEOUT = 60
MAX_ATTEMPTS = 5
RETRY_DELAY_SEC = 1.0
SCHEME_ATTEMPTS = 1

# TPathId is invalid when either component is Max<ui64>().
INVALID_PATH_ID = (1 << 64) - 1
TX_LIST_HEADERS = ('opid', 'type', 'state', 'shards in progress')
ROLE_BY_LABEL = {
    'targetpathid': 'target',
    'sourcepathid': 'source',
    'cdcpathid': 'cdc',
}
ROLE_ORDER = {'target': 0, 'source': 1, 'cdc': 2}
GONE_MARKERS = (
    'Unknown Tx',
    'No txState for operation',
    'No operations for tx id',
    'No suboperations for operation',
)

_THREAD_LOCAL = threading.local()


def log(msg, file=sys.stderr):
    print(f'[{time.ctime()}] {msg}', file=file, flush=True)


def one_line(text):
    return ' '.join(str(text).split())


def normalize_path(path):
    path = (path or '').strip().replace('\\', '/')
    if not path.startswith('/'):
        path = '/' + path
    while '//' in path:
        path = path.replace('//', '/')
    if len(path) > 1:
        path = path.rstrip('/')
    return path


def as_int(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value != value:
            return None
        return int(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text, 10)
    except ValueError:
        return None


def norm_status(status):
    if status is None:
        return None
    text = str(status).strip()
    if '.' in text:
        text = text.rsplit('.', 1)[-1]
    return text.upper()


def describe_is_success(payload):
    if not isinstance(payload, dict):
        return False
    status = payload.get('Status')
    if status is None:
        return 'PathDescription' in payload
    name = norm_status(status)
    return name in ('0', 'STATUSSUCCESS', 'SUCCESS', 'OK')


def extract_schemeshard_id(describe):
    """SchemeShard tablet of the database, or None."""
    if not isinstance(describe, dict):
        return None
    domain = (describe.get('PathDescription') or {}).get('DomainDescription') or {}
    processing = domain.get('ProcessingParams') or {}
    for key in ('SchemeShard', 'schemeShard', 'schemeshard'):
        found = as_int(processing.get(key))
        if found:
            return found
    return None


def is_access_denied(value):
    text = str(value).lower().replace('ё', 'е')
    markers = (
        'access denied',
        'доступ запрещ',
        'unauthorized',
        'forbidden',
        'permission denied',
        'http 401',
        'http 403',
        '401 client error',
        '403 client error',
    )
    return any(marker in text for marker in markers)


def is_connection_error(exc):
    if is_access_denied(exc) or isinstance(exc, requests.exceptions.HTTPError):
        return False
    if isinstance(exc, (
        requests.exceptions.ConnectionError,
        requests.exceptions.ChunkedEncodingError,
        ConnectionError,
        ConnectionResetError,
        ConnectionAbortedError,
        BrokenPipeError,
    )):
        return True
    text = str(exc).lower()
    return any(marker in text for marker in (
        'connection aborted',
        'connection reset',
        'connection broken',
        'connection refused',
        'connection error',
        'remote end closed',
        'remote disconnected',
        'broken pipe',
        'разрыв соединения',
        'ошибка соединения',
    ))


def call_with_connection_retries(operation, what, attempts=None):
    total = SCHEME_ATTEMPTS if attempts is None else attempts
    if total < 1:
        total = 1
    for attempt in range(1, total + 1):
        try:
            return operation()
        except Exception as exc:
            if attempt >= total or not is_connection_error(exc) or is_access_denied(exc):
                raise
            delay = RETRY_DELAY_SEC * attempt
            log(
                f'Retry {what} ({attempt}/{total}): {one_line(exc)}; '
                f'sleeping {delay:.1f}s'
            )
            time.sleep(delay)


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


def get_session():
    session = getattr(_THREAD_LOCAL, 'session', None)
    if session is None:
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=4,
            pool_maxsize=4,
            max_retries=0,
        )
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        _THREAD_LOCAL.session = session
    return session


def load_json(url):
    response = get_session().get(
        url, headers=VIEWER_HEADERS, verify=False, timeout=HTTP_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def load_text(url):
    response = get_session().get(
        url,
        headers=VIEWER_HEADERS,
        verify=False,
        timeout=HTTP_TIMEOUT,
        allow_redirects=False,
    )
    if 300 <= response.status_code < 400:
        raise requests.exceptions.HTTPError(
            f'HTTP {response.status_code} redirect',
            response=response,
        )
    response.raise_for_status()
    content_type = response.headers.get('Content-Type', '')
    if 'charset=' not in content_type.lower():
        response.encoding = 'utf-8'
    return response.text


def describe_url(database):
    query = '&'.join((
        f'database={quote(database, safe="/")}',
        f'path={quote(database, safe="/")}',
        'enums=true',
        'children=false',
        'partitioning_info=false',
        'partition_config=false',
        'backup=false',
    ))
    return URL_DESCRIBE.format(url_base=VIEWER_URL_BASE, query=query)


def describe_database(database):
    """Single attempt. A failure here usually means ``--viewer-url`` is wrong."""
    url = describe_url(database)
    return call_with_connection_retries(lambda: load_json(url), f'describe {database}', 1)


def tablet_url(schemeshard_id, **params):
    parts = [f'TabletID={schemeshard_id}']
    for key, value in params.items():
        parts.append(f'{key}={value}')
    query = '&'.join(parts)
    return f'{URL_TABLET_APP.format(url_base=VIEWER_URL_BASE)}?{query}'


def cgi_params(href):
    href = unescape(href or '')
    query = href.split('?', 1)[-1]
    parsed = parse_qs(query, keep_blank_values=False)
    result = {}
    for key, values in parsed.items():
        if values:
            result[key] = values[-1]
    return result


def is_valid_path_id(owner, local):
    if owner is None or local is None:
        return False
    return owner != INVALID_PATH_ID and local != INVALID_PATH_ID


class _HtmlTables(HTMLParser):
    """Collect rows of every HTML table, including tables nested in a layout."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self._stack = []
        self._row = None
        self._cell = None

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attrs = {key.lower(): value for key, value in attrs}
        if tag == 'table':
            self._stack.append([])
            self._row = None
            self._cell = None
            return
        if not self._stack:
            return
        if tag == 'tr':
            self._row = []
            self._cell = None
        elif tag in ('td', 'th') and self._row is not None:
            self._cell = {'text': [], 'href': None, 'header': tag == 'th'}
        elif tag == 'a' and self._cell is not None and not self._cell['href']:
            self._cell['href'] = attrs.get('href')

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in ('td', 'th') and self._cell is not None and self._row is not None:
            text = ' '.join(''.join(self._cell['text']).split())
            self._row.append({
                'text': text,
                'href': self._cell['href'],
                'header': self._cell['header'],
            })
            self._cell = None
        elif tag == 'tr' and self._row is not None and self._stack:
            if self._row:
                self._stack[-1].append(self._row)
            self._row = None
        elif tag == 'table' and self._stack:
            self.tables.append(self._stack.pop())
            self._row = None
            self._cell = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell['text'].append(data)


def _op_ids(href, text):
    params = cgi_params(href)
    tx_id = as_int(params.get('TxId'))
    part_id = as_int(params.get('PartId'))
    if tx_id is None or part_id is None:
        left, sep, right = (text or '').partition(':')
        if sep:
            tx_id = as_int(left)
            part_id = as_int(right)
    return tx_id, part_id


def parse_tx_list(html):
    """Return in-flight sub-operations from a ``Page=TxList`` body.

    Each item has ``tx_id``, ``part_id``, ``tx_type``, ``state``, and
    ``shards``. Raises ``RuntimeError`` when the transaction table is absent.
    """
    parser = _HtmlTables()
    parser.feed(html or '')
    parser.close()
    for table in parser.tables:
        if not table:
            continue
        header = tuple(cell['text'].strip().lower() for cell in table[0])
        if header[:len(TX_LIST_HEADERS)] != TX_LIST_HEADERS:
            continue
        operations = []
        for row in table[1:]:
            if len(row) < 4 or row[0]['header']:
                continue
            tx_id, part_id = _op_ids(row[0].get('href'), row[0]['text'])
            if tx_id is None or part_id is None:
                raise RuntimeError(
                    f'in-flight row has no transaction id: {row[0]["text"]!r}'
                )
            operations.append({
                'tx_id': tx_id,
                'part_id': part_id,
                'tx_type': row[1]['text'],
                'state': row[2]['text'],
                'shards': row[3]['text'],
            })
        return operations
    snippet = one_line(html or '')[:180]
    raise RuntimeError(f'in-flight transaction table not found: {snippet}')


_TX_PATH_LINK = re.compile(
    r"""(TargetPathId|SourcePathId|CdcPathId):\s*<a\s+href=(['"])(.*?)\2""",
    re.IGNORECASE,
)
_PATH_LINE = re.compile(r'(?m)(?:^|>)\s*Path: ([^\n]*)')


def parse_tx_info(html):
    """Return ``(refs, status)`` for a ``Page=TxInfo`` body.

    ``refs`` is a list of ``{role, owner, local}``. ``status`` is ``ok``,
    ``gone`` when the transaction has already left ``TxInFlight``, or
    ``unparsed`` when the page has neither path ids nor that notice.
    """
    refs = []
    seen = set()
    found_label = False
    for match in _TX_PATH_LINK.finditer(html or ''):
        found_label = True
        role = ROLE_BY_LABEL.get(match.group(1).lower())
        if not role:
            continue
        params = cgi_params(match.group(3))
        owner = as_int(params.get('OwnerPathId'))
        local = as_int(params.get('LocalPathId'))
        if not is_valid_path_id(owner, local):
            continue
        key = (role, owner, local)
        if key in seen:
            continue
        seen.add(key)
        refs.append({'role': role, 'owner': owner, 'local': local})
    refs.sort(key=lambda ref: ROLE_ORDER[ref['role']])
    if found_label:
        return refs, 'ok'
    text = unescape(html or '')
    if any(marker in text for marker in GONE_MARKERS):
        return [], 'gone'
    return [], 'unparsed'


def parse_path_info(html):
    """Return ``(path, error)`` from a ``Page=PathInfo`` body.

    SchemeShard prints the path as ``<pre>Path: /full/path`` with no newline
    between the tag and the label.
    """
    for raw in _PATH_LINE.findall(html or ''):
        path = unescape(raw).strip()
        if path:
            return path, ''
    if html and 'No path item for pathId' in html:
        return '', 'path not found'
    return '', 'path page has no Path field'


def operation_line(operation, role, path):
    return (
        f'{operation["tx_id"]}\t{operation["part_id"]}\t{operation["tx_type"]}'
        f'\t{operation["state"]}\t{operation["shards"]}\t{role}\t{one_line(path)}'
    )


def load_tx_list(schemeshard_id):
    url = tablet_url(schemeshard_id, Page='TxList')
    html = call_with_connection_retries(
        lambda: load_text(url), f'schemeshard {schemeshard_id} TxList',
    )
    return parse_tx_list(html)


def load_tx_info(schemeshard_id, operation):
    label = f'{operation["tx_id"]}:{operation["part_id"]}'
    url = tablet_url(
        schemeshard_id,
        Page='TxInfo',
        TxId=operation['tx_id'],
        PartId=operation['part_id'],
    )
    try:
        html = call_with_connection_retries(
            lambda: load_text(url), f'transaction {label}',
        )
    except Exception as exc:
        return {**operation, 'refs': [], 'error': one_line(exc), 'status': 'error'}
    refs, status = parse_tx_info(html)
    if status == 'gone':
        return {**operation, 'refs': [], 'error': '', 'status': 'gone'}
    if status == 'unparsed':
        return {
            **operation,
            'refs': [],
            'error': 'transaction page has no affected paths',
            'status': 'error',
        }
    return {**operation, 'refs': refs, 'error': '', 'status': 'ok'}


def load_object_path(schemeshard_id, owner, local):
    url = tablet_url(
        schemeshard_id,
        Page='PathInfo',
        OwnerPathId=owner,
        LocalPathId=local,
    )
    label = f'{owner}:{local}'
    try:
        html = call_with_connection_retries(
            lambda: load_text(url), f'path {label}',
        )
    except Exception as exc:
        return (owner, local), '', f'{one_line(exc)} ({label})'
    path, error = parse_path_info(html)
    if error:
        error = f'{error} ({label})'
    return (owner, local), path, error


def iter_rows(operations, paths):
    """Yield ``(line, is_error)`` in transaction order."""
    ordered = sorted(operations, key=lambda item: (item['tx_id'], item['part_id']))
    for operation in ordered:
        if operation['status'] == 'gone':
            continue
        if operation['error']:
            yield operation_line(operation, '', f'ERROR: {operation["error"]}'), True
            continue
        if not operation['refs']:
            yield operation_line(operation, '', ''), False
            continue
        for ref in operation['refs']:
            key = (ref['owner'], ref['local'])
            path, error = paths.get(key, ('', 'path was not resolved'))
            if error:
                yield operation_line(operation, ref['role'], f'ERROR: {error}'), True
            else:
                yield operation_line(operation, ref['role'], path), False


def main():
    global VIEWER_URL_BASE, HTTP_TIMEOUT, SCHEME_ATTEMPTS

    parser = ArgumentParser(
        formatter_class=RawDescriptionHelpFormatter,
        description=__doc__,
        epilog='''\
Examples:
  %(prog)s --viewer-url https://host:8765 --auth Login /Root/database

  %(prog)s --viewer-url https://host:8765 --auth Login \\
      --schemeshard-id 72075186224037888 /Root/database
''',
    )
    parser.add_argument('--viewer-url', required=True)
    parser.add_argument('--auth', dest='auth_mode', default='Login')
    parser.add_argument(
        'database',
        help='Database path used to find the SchemeShard id (e.g. /Root/database)',
    )
    parser.add_argument(
        '--schemeshard-id',
        default=None,
        help='SchemeShard tablet id. Default: read it from the database description',
    )
    parser.add_argument(
        '--threads',
        type=int,
        default=4,
        help='Parallel transaction and path lookups (default: 4)',
    )
    parser.add_argument(
        '--retries',
        type=int,
        default=MAX_ATTEMPTS,
        help=(
            'Attempts after a dropped or failed connection while reading '
            f'transactions and paths (default: {MAX_ATTEMPTS}). '
            'The initial SchemeShard lookup is a single attempt. '
            'Access denied is not retried.'
        ),
    )
    parser.add_argument(
        '--timeout',
        type=float,
        default=HTTP_TIMEOUT,
        help=f'HTTP timeout in seconds (default: {HTTP_TIMEOUT})',
    )
    args = parser.parse_args()

    if args.threads < 1:
        parser.error('--threads must be >= 1')
    if args.retries < 1:
        parser.error('--retries must be >= 1')
    if args.timeout <= 0:
        parser.error('--timeout must be > 0')

    database = normalize_path(args.database)
    setup_auth(args.auth_mode)
    VIEWER_URL_BASE = args.viewer_url.rstrip('/')
    HTTP_TIMEOUT = args.timeout
    SCHEME_ATTEMPTS = args.retries

    schemeshard_id = as_int(args.schemeshard_id) if args.schemeshard_id else None
    if args.schemeshard_id and not schemeshard_id:
        parser.error(f'invalid --schemeshard-id {args.schemeshard_id!r}')
    if schemeshard_id is None:
        log(f'Resolving SchemeShard for {database}')
        try:
            described = describe_database(database)
        except Exception as exc:
            print(f'Failed to describe {database}: {exc}', file=sys.stderr)
            sys.exit(1)
        if not describe_is_success(described):
            status = described.get('Status') if isinstance(described, dict) else described
            reason = described.get('Reason') if isinstance(described, dict) else ''
            message = f'describe status {status}'
            if reason:
                message = f'{message}: {reason}'
            print(f'Failed to describe {database}: {one_line(message)}', file=sys.stderr)
            sys.exit(1)
        schemeshard_id = extract_schemeshard_id(described)
        if not schemeshard_id:
            print(
                f'SchemeShard id not found in describe of {database}. '
                'Pass --schemeshard-id explicitly.',
                file=sys.stderr,
            )
            sys.exit(1)
    log(f'SchemeShard {schemeshard_id}')

    try:
        operations = load_tx_list(schemeshard_id)
    except Exception as exc:
        print(
            f'Failed to list in-flight transactions of SchemeShard {schemeshard_id}: '
            f'{one_line(exc)}',
            file=sys.stderr,
        )
        sys.exit(1)
    log(f'In-flight sub-operations: {len(operations)}')
    if not operations:
        return

    workers = min(args.threads, len(operations))
    detailed = []
    with ThreadPool(workers) as pool:
        for item in pool.imap_unordered(
            lambda operation: load_tx_info(schemeshard_id, operation),
            operations,
        ):
            detailed.append(item)

    path_keys = []
    seen_paths = set()
    for item in detailed:
        for ref in item['refs']:
            key = (ref['owner'], ref['local'])
            if key not in seen_paths:
                seen_paths.add(key)
                path_keys.append(key)

    paths = {}
    if path_keys:
        path_workers = min(args.threads, len(path_keys))
        with ThreadPool(path_workers) as pool:
            for key, path, error in pool.imap_unordered(
                lambda key: load_object_path(schemeshard_id, key[0], key[1]),
                path_keys,
            ):
                paths[key] = (path, error)

    gone = sum(1 for item in detailed if item['status'] == 'gone')
    if gone:
        log(f'Skipped {gone} sub-operation(s) that finished before details were read')

    errors = 0
    printed = 0
    for line, is_error in iter_rows(detailed, paths):
        if is_error:
            errors += 1
            log(line)
        print(line, flush=True)
        printed += 1
    log(f'Done: rows={printed}, errors={errors}')
    if errors:
        sys.exit(2)


if __name__ == '__main__':
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    main()
