#!/usr/bin/env python3
"""Resolve a Hive tablet id to the scheme object that owns it.

Schemeshard stores the object's local path id in the Hive tablet record
(``ObjectId``) and its schemeshard id in ``TabletOwner.Owner``. This script
reads that record from ``/viewer/json/hiveinfo`` and describes the path id.

Prints ``tablet_id``, full scheme path, and scheme type (``TABLE``,
``TOPIC``, ``COLUMN_TABLE``, ...). A PersQueue group, including a CDC
``streamImpl``, is reported as ``TOPIC``.

The database describe that finds the Hive id is a single attempt. A dropped
or failed connection while reading Hive or the scheme object is retried.
Access denied is not retried. Describing by path id needs monitoring access.

Auth: ``--auth Login`` (or OAuth) and a token in ``~/.ydb/token``.
"""

import os
import sys
import threading
import time
import requests
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from multiprocessing.pool import ThreadPool
from urllib.parse import quote

VIEWER_URL_BASE = ''
VIEWER_HEADERS = {}

URL_DESCRIBE = '{url_base}/viewer/json/describe?{query}'
URL_HIVE_INFO = (
    '{url_base}/viewer/json/hiveinfo?hive_id={hive_id}'
    '&tablet_id={tablet_id}&enums=true&ui64=true'
)

HTTP_TIMEOUT = 60
MAX_ATTEMPTS = 5
RETRY_DELAY_SEC = 1.0
SCHEME_ATTEMPTS = 1

# NKikimrSchemeOp.EPathType. PersQueueGroup is shown as TOPIC.
SCHEME_TYPE_BY_NUMBER = {
    1: 'DIRECTORY',
    2: 'TABLE',
    3: 'TOPIC',
    4: 'DATABASE',
    9: 'TABLE_INDEX',
    10: 'DATABASE',
    12: 'COLUMN_STORE',
    13: 'COLUMN_TABLE',
    14: 'CDC_STREAM',
    15: 'SEQUENCE',
    16: 'REPLICATION',
    17: 'BLOB_DEPOT',
    20: 'VIEW',
}
SCHEME_TYPE_ALIASES = {
    'DIR': 'DIRECTORY',
    'SUBDOMAIN': 'DATABASE',
    'EXTSUBDOMAIN': 'DATABASE',
    'PERSQUEUEGROUP': 'TOPIC',
    'PERS_QUEUE_GROUP': 'TOPIC',
    'CDCSTREAM': 'CDC_STREAM',
    'TABLEINDEX': 'TABLE_INDEX',
    'COLUMNSTORE': 'COLUMN_STORE',
    'COLUMNTABLE': 'COLUMN_TABLE',
}

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


def scheme_type_name(value):
    if value is None:
        return ''
    if isinstance(value, int):
        return SCHEME_TYPE_BY_NUMBER.get(value, str(value))
    text = str(value).strip()
    if text.isdigit():
        return SCHEME_TYPE_BY_NUMBER.get(int(text), text)
    if '.' in text:
        text = text.rsplit('.', 1)[-1]
    text = text.upper()
    for prefix in ('EPATHTYPE', 'EPATHSUBTYPE'):
        if text.startswith(prefix):
            text = text[len(prefix):]
            break
    return SCHEME_TYPE_ALIASES.get(text, text)


def describe_is_success(payload):
    if not isinstance(payload, dict):
        return False
    status = payload.get('Status')
    if status is None:
        return 'PathDescription' in payload
    name = norm_status(status)
    return name in ('0', 'STATUSSUCCESS', 'SUCCESS', 'OK')


def extract_hive_id(describe):
    """Dedicated Hive (ProcessingParams.Hive) wins over SharedHive."""
    if not isinstance(describe, dict):
        return None
    domain = (describe.get('PathDescription') or {}).get('DomainDescription') or {}
    processing = domain.get('ProcessingParams') or {}
    hive = as_int(processing.get('Hive'))
    if hive:
        return hive
    shared = as_int(domain.get('SharedHive'))
    if shared:
        return shared
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


def describe_url(database, **params):
    query = '&'.join(
        f'{key}={quote(str(value), safe="/")}'
        for key, value in params.items()
        if value is not None and value != ''
    )
    if database:
        query = f'database={quote(database, safe="/")}&{query}'
    return URL_DESCRIBE.format(url_base=VIEWER_URL_BASE, query=query)


def describe_database(database):
    """Single attempt. A failure here usually means ``--viewer-url`` is wrong."""
    url = describe_url(
        database,
        path=database,
        enums='true',
        children='false',
        partitioning_info='false',
        partition_config='false',
        backup='false',
    )
    return call_with_connection_retries(lambda: load_json(url), f'describe {database}', 1)


def hive_info(hive_id, tablet_id):
    url = URL_HIVE_INFO.format(
        url_base=VIEWER_URL_BASE,
        hive_id=hive_id,
        tablet_id=tablet_id,
    )
    return call_with_connection_retries(
        lambda: load_json(url), f'hiveinfo tablet {tablet_id}',
    )


def describe_object(database, schemeshard_id, path_id):
    url = describe_url(
        database,
        path_id=path_id,
        schemeshard_id=schemeshard_id,
        enums='true',
        children='false',
        partitioning_info='false',
        partition_config='false',
        backup='false',
    )
    return call_with_connection_retries(
        lambda: load_json(url), f'describe path_id {path_id}',
    )


def _field(entry, *names):
    if not isinstance(entry, dict):
        return None
    for name in names:
        if name in entry:
            return entry[name]
    return None


def pick_hive_tablet(payload, tablet_id):
    """Return the leader record for ``tablet_id``, or None."""
    if not isinstance(payload, dict):
        return None
    tablets = _field(payload, 'Tablets', 'tablets') or []
    matches = []
    for tablet in tablets:
        if not isinstance(tablet, dict):
            continue
        found = as_int(_field(tablet, 'TabletID', 'TabletId', 'tabletId'))
        if found == tablet_id:
            matches.append(tablet)
    if not matches:
        return None
    matches.sort(key=lambda tablet: as_int(_field(tablet, 'FollowerID', 'FollowerId')) or 0)
    return matches[0]


def hive_object_ref(tablet):
    """Return ``(schemeshard_id, local_path_id, tablet_type)`` from a Hive record.

    ``ObjectId`` is the scheme object's local path id. ``TabletOwner.Owner``
    is the schemeshard that owns that path.
    """
    owner = _field(tablet, 'TabletOwner', 'tabletOwner') or {}
    schemeshard_id = as_int(_field(owner, 'Owner', 'owner'))
    path_id = as_int(_field(tablet, 'ObjectId', 'objectId'))
    tablet_type = _field(tablet, 'TabletType', 'tabletType')
    if tablet_type is None:
        tablet_type = ''
    else:
        tablet_type = str(tablet_type)
        if '.' in tablet_type:
            tablet_type = tablet_type.rsplit('.', 1)[-1]
    return schemeshard_id, path_id, tablet_type


def scheme_object(describe):
    """Return ``(path, scheme_type)`` from a describe response."""
    if not isinstance(describe, dict):
        return '', ''
    path = _field(describe, 'Path', 'path') or ''
    self_entry = (_field(describe, 'PathDescription', 'pathDescription') or {}).get('Self') or {}
    if not self_entry:
        self_entry = (_field(describe, 'PathDescription', 'pathDescription') or {}).get('self') or {}
    kind = scheme_type_name(_field(self_entry, 'PathType', 'pathType', 'type', 'Type'))
    return str(path), kind


def resolve_tablet(database, hive_id, tablet_id):
    """Return ``(path, scheme_type)`` or raise ``RuntimeError``."""
    try:
        hive_payload = hive_info(hive_id, tablet_id)
    except Exception as exc:
        raise RuntimeError(one_line(exc)) from exc
    tablet = pick_hive_tablet(hive_payload, tablet_id)
    if tablet is None:
        raise RuntimeError(f'tablet {tablet_id} not found in hive {hive_id}')
    schemeshard_id, path_id, tablet_type = hive_object_ref(tablet)
    if not schemeshard_id or not path_id:
        detail = f'tablet type {tablet_type}' if tablet_type else 'no tablet type'
        raise RuntimeError(f'no scheme object ({detail})')
    try:
        described = describe_object(database, schemeshard_id, path_id)
    except Exception as exc:
        raise RuntimeError(one_line(exc)) from exc
    if not describe_is_success(described):
        status = described.get('Status') if isinstance(described, dict) else described
        reason = described.get('Reason') if isinstance(described, dict) else ''
        message = f'describe status {status}'
        if reason:
            message = f'{message}: {reason}'
        raise RuntimeError(one_line(message))
    path, kind = scheme_object(described)
    if not path or not kind:
        raise RuntimeError('describe has no path or type')
    return path, kind


def result_line(tablet_id, path, kind, error):
    if error:
        return f'{tablet_id}\t\t{one_line(error)}'
    return f'{tablet_id}\t{path}\t{kind}'


def main():
    global VIEWER_URL_BASE, HTTP_TIMEOUT, SCHEME_ATTEMPTS

    parser = ArgumentParser(
        formatter_class=RawDescriptionHelpFormatter,
        description=__doc__,
        epilog='''\
Examples:
  %(prog)s --viewer-url https://host:8765 --auth Login \\
      /Root/database 72075186224123090

  %(prog)s --viewer-url https://host:8765 --auth Login \\
      /Root/database 72075186224123090 72075186224123091
''',
    )
    parser.add_argument('--viewer-url', required=True)
    parser.add_argument('--auth', dest='auth_mode', default='Login')
    parser.add_argument(
        'database',
        help='Database path used to find the Hive id (e.g. /Root/database)',
    )
    parser.add_argument(
        'tablet_id',
        nargs='+',
        help='One or more Hive tablet ids',
    )
    parser.add_argument(
        '--hive-id',
        default=None,
        help='Hive tablet id. Default: read it from the database description',
    )
    parser.add_argument(
        '--threads',
        type=int,
        default=4,
        help='Parallel lookups (default: 4)',
    )
    parser.add_argument(
        '--retries',
        type=int,
        default=MAX_ATTEMPTS,
        help=(
            'Attempts after a dropped or failed connection while reading '
            f'Hive or the scheme object (default: {MAX_ATTEMPTS}). '
            'The initial Hive lookup is a single attempt. '
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

    tablet_ids = []
    for raw in args.tablet_id:
        tablet_id = as_int(raw)
        if not tablet_id:
            parser.error(f'invalid tablet id {raw!r}')
        tablet_ids.append(tablet_id)

    database = normalize_path(args.database)
    setup_auth(args.auth_mode)
    VIEWER_URL_BASE = args.viewer_url.rstrip('/')
    HTTP_TIMEOUT = args.timeout
    SCHEME_ATTEMPTS = args.retries

    hive_id = as_int(args.hive_id) if args.hive_id else None
    if args.hive_id and not hive_id:
        parser.error(f'invalid --hive-id {args.hive_id!r}')
    if hive_id is None:
        log(f'Resolving Hive for {database}')
        try:
            hive_id = extract_hive_id(describe_database(database))
        except Exception as exc:
            print(f'Failed to describe {database}: {exc}', file=sys.stderr)
            sys.exit(1)
        if not hive_id:
            print(
                f'Hive id not found in describe of {database}. '
                'Pass --hive-id explicitly.',
                file=sys.stderr,
            )
            sys.exit(1)
    log(f'Hive {hive_id}, resolving {len(tablet_ids)} tablet(s)')

    def lookup(tablet_id):
        try:
            path, kind = resolve_tablet(database, hive_id, tablet_id)
        except Exception as exc:
            log(f'{tablet_id}: {exc}')
            return tablet_id, '', '', str(exc)
        log(f'{tablet_id} -> {path} {kind}')
        return tablet_id, path, kind, ''

    rows = []
    with ThreadPool(min(args.threads, len(tablet_ids))) as pool:
        for tablet_id, path, kind, error in pool.imap_unordered(lookup, tablet_ids):
            rows.append((tablet_id, path, kind, error))
    order = {tablet_id: index for index, tablet_id in enumerate(tablet_ids)}
    rows.sort(key=lambda row: order[row[0]])
    errors = 0
    for tablet_id, path, kind, error in rows:
        if error:
            errors += 1
        print(result_line(tablet_id, path, kind, f'ERROR: {error}' if error else ''), flush=True)
    log(f'Done: tablets={len(rows)}, errors={errors}')
    if errors:
        sys.exit(2)


if __name__ == '__main__':
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    main()
