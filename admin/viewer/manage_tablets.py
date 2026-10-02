#!/usr/bin/env python3
"""Stop or start Hive-managed tablets of schema objects of a given kind.

Default kind is PQ: tablets of topic objects (scheme types TOPIC and
PERS_QUEUE_GROUP), including hidden CDC changefeed topics
``{table}/{stream}/streamImpl`` and the same topics under a secondary
index, ``{table}/{index}/{impl}/{stream}/streamImpl``. ``--type TABLE``
includes DataShard tablets of the table and of its secondary-index
implementation tables (usually ``indexImplTable``). A path prefix limits
which objects are included. Default action is stop; ``--action start``
resumes the same set.

Discovery uses the Embedded UI Web API:

* ``GET /scheme/directory`` — walk the schema tree (same as find_legacy_tables.py)
* ``GET /viewer/json/describe`` — read tablet ids from PathDescription
* database describe — Hive id from DomainDescription.ProcessingParams.Hive,
  or SharedHive when the database has no dedicated Hive

Both actions are Hive monitoring handlers in ydb/core/mind/hive/monitoring.cpp:

    POST /tablets/app?TabletID=<hive>&page=StopTablet&tablet=<id>&wait=true
    POST /tablets/app?TabletID=<hive>&page=ResumeTablet&tablet=<id>&wait=true

A stopped tablet stays down until ResumeTablet. Reply status ALREADY means
the tablet is already stopped or already running and is counted as success.

Auth: ``--auth Login`` (or OAuth) and a token in ``~/.ydb/token``.
"""

import json
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

URL_SCHEME_DIRECTORY = '{url_base}/scheme/directory?database={database}&path={path}'
URL_DESCRIBE = '{url_base}/viewer/json/describe?path={path}&enums=true'
URL_TABLET_APP = '{url_base}/tablets/app'

HTTP_TIMEOUT = 60
MAX_ATTEMPTS = 5
RETRY_DELAY_SEC = 1.0

# Hive monitoring page and stdout labels for each --action.
# start is Hive ResumeTablet: it boots a tablet that was previously stopped.
ACTIONS = {
    'stop': {
        'page': 'StopTablet',
        'done': 'stopped',
        'already': 'already-stopped',
    },
    'start': {
        'page': 'ResumeTablet',
        'done': 'started',
        'already': 'already-running',
    },
}
ACTION_ALIASES = {
    'resume': 'start',
}

DIRECTORY_TYPES = frozenset({'DIRECTORY', 'DATABASE', 'COLUMN_STORE'})
TOPIC_SCHEME_TYPES = frozenset({'TOPIC', 'PERS_QUEUE_GROUP'})

# --type value -> scheme entry types to select.
# PQ is the default and means topic objects, including legacy persqueue groups.
KIND_SCHEME_TYPES = {
    'PQ': TOPIC_SCHEME_TYPES,
    'TOPIC': TOPIC_SCHEME_TYPES,
    'PERS_QUEUE_GROUP': frozenset({'PERS_QUEUE_GROUP'}),
    'TABLE': frozenset({'TABLE'}),
    'COLUMN_TABLE': frozenset({'COLUMN_TABLE'}),
    'COLUMN_STORE': frozenset({'COLUMN_STORE'}),
}

# Numeric Ydb.Scheme.Entry.Type values, in case the directory listing
# returns enums as numbers.
SCHEME_TYPE_BY_NUMBER = {
    1: 'DIRECTORY',
    2: 'TABLE',
    3: 'PERS_QUEUE_GROUP',
    4: 'DATABASE',
    9: 'TABLE_INDEX',
    12: 'COLUMN_STORE',
    13: 'COLUMN_TABLE',
    14: 'CDC_STREAM',
    17: 'TOPIC',
}

# Internal EPathType / EPathSubType names as returned by /viewer/json/describe.
SCHEME_TYPE_ALIASES = {
    'DIR': 'DIRECTORY',
    'SUBDOMAIN': 'DATABASE',
    'EXTSUBDOMAIN': 'DATABASE',
    'PERSQUEUEGROUP': 'PERS_QUEUE_GROUP',
    'CDCSTREAM': 'CDC_STREAM',
    'TABLEINDEX': 'TABLE_INDEX',
    'COLUMNSTORE': 'COLUMN_STORE',
    'COLUMNTABLE': 'COLUMN_TABLE',
    'STREAMIMPL': 'STREAM_IMPL',
}

# Child of a secondary index that holds its DataShard tablets.
# Vector and fulltext indexes can have several such children; their names
# come from a describe of the index. This name is the global-index fallback.
INDEX_IMPL_NAME = 'indexImplTable'
LOCAL_INDEX_TYPES = frozenset({
    'LOCALBLOOMFILTER',
    'LOCALBLOOMNGRAMFILTER',
    'LOCALMINMAX',
    'LOCALCOUNTMINSKETCH',
})
INDEX_TYPE_BY_NUMBER = {
    0: 'INVALID',
    1: 'GLOBAL',
    2: 'GLOBALASYNC',
    3: 'GLOBALUNIQUE',
    4: 'GLOBALVECTORKMEANSTREE',
    5: 'GLOBALFULLTEXTPLAIN',
    6: 'GLOBALFULLTEXTRELEVANCE',
    7: 'GLOBALJSON',
    8: 'LOCALBLOOMFILTER',
    9: 'LOCALBLOOMNGRAMFILTER',
    10: 'LOCALMINMAX',
    11: 'GLOBALFULLTEXTCOMPACT',
    12: 'GLOBALFULLTEXTCOMPACTRELEVANCE',
    13: 'GLOBALJSONCOMPACT',
    14: 'LOCALCOUNTMINSKETCH',
}

# Child of a CDC stream created by schemeshard (ESchemeOpCreatePersQueueGroup).
CDC_IMPL_NAME = 'streamImpl'
CDC_DESCRIBE_QUERY = (
    'children=true&partitioning_info=false&partition_config=false&backup=false'
)

SUCCESS_STATUSES = frozenset({'0', 'OK', '2', 'ALREADY'})
ALREADY_STATUSES = frozenset({'2', 'ALREADY'})

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


def join_path(parent, name):
    return f'{parent.rstrip("/")}/{name}'


def paths_intersect(path, prefix):
    """True when ``path`` is under ``prefix`` or ``prefix`` is under ``path``."""
    return prefix is None or path_matches_prefix(path, prefix) or path_matches_prefix(prefix, path)


def path_matches_prefix(path, prefix):
    """Path-boundary prefix: equal to prefix, or a child of it.

    ``/db/orders`` matches ``/db/orders`` and ``/db/orders/topic``,
    and does not match ``/db/orders_old``.
    ``prefix is None`` matches every path.
    """
    if prefix is None:
        return True
    path = normalize_path(path)
    prefix = normalize_path(prefix)
    return path == prefix or path.startswith(prefix + '/')


def resolve_prefix(database, prefix):
    """Return a normalized absolute prefix, or None when unset."""
    if prefix is None or str(prefix).strip() == '':
        return None
    database = normalize_path(database)
    raw = str(prefix).strip()
    if not raw.startswith('/'):
        raw = join_path(database, raw)
    prefix = normalize_path(raw)
    if not path_matches_prefix(prefix, database):
        raise ValueError(
            f'path prefix {prefix} is outside database {database}'
        )
    return prefix


def parse_kinds(text):
    """Return (scheme_types, kind_names) for a comma-separated --type list."""
    names = []
    scheme_types = set()
    for part in str(text).split(','):
        name = part.strip().upper()
        if not name:
            continue
        if name not in KIND_SCHEME_TYPES:
            known = ', '.join(sorted(KIND_SCHEME_TYPES))
            raise ValueError(f'unknown type {name!r}; known types: {known}')
        names.append(name)
        scheme_types.update(KIND_SCHEME_TYPES[name])
    if not names:
        raise ValueError('--type is empty')
    return frozenset(scheme_types), names


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


def as_int(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value != value:  # NaN
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


def is_deleted_partition(status):
    name = norm_status(status)
    return name in ('3', 'DELETED')


def describe_is_success(payload):
    if not isinstance(payload, dict):
        return False
    status = payload.get('Status')
    if status is None:
        return 'PathDescription' in payload
    name = norm_status(status)
    return name in ('0', 'STATUSSUCCESS', 'SUCCESS', 'OK')


def extract_hive_id(describe):
    """Hive tablet that owns the database, or None.

    Dedicated Hive (ProcessingParams.Hive) wins over SharedHive.
    """
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


def _add_tablet(tablets, tablet_id, role, part_id=None):
    if not tablet_id:
        return
    rec = tablets.get(tablet_id)
    if rec is None:
        rec = {'role': role, 'parts': []}
        tablets[tablet_id] = rec
    elif role == 'balancer' and rec['role'] != 'balancer':
        if not rec['role'].endswith('+balancer'):
            rec['role'] = rec['role'] + '+balancer'
    if part_id is not None and part_id not in rec['parts']:
        rec['parts'].append(part_id)


def extract_topic_tablets(describe):
    """Partition (PersQueue) tablets and the read-balancer tablet of a topic."""
    pq = ((describe.get('PathDescription') or {}).get('PersQueueGroup') or {})
    if not pq:
        return None
    tablets = {}
    for part in pq.get('Partitions') or []:
        if not isinstance(part, dict):
            continue
        if is_deleted_partition(part.get('Status')):
            continue
        _add_tablet(
            tablets,
            as_int(part.get('TabletId')),
            'partition',
            as_int(part.get('PartitionId')),
        )
    _add_tablet(tablets, as_int(pq.get('BalancerTabletID')), 'balancer')
    return tablets


def extract_table_tablets(describe):
    path_description = describe.get('PathDescription') or {}
    if 'Table' not in path_description and 'TablePartitions' not in path_description:
        return None
    tablets = {}
    for part in path_description.get('TablePartitions') or []:
        if not isinstance(part, dict):
            continue
        _add_tablet(tablets, as_int(part.get('DatashardId')), 'datashard')
    return tablets


def _column_shard_ids(values):
    ids = []
    for value in values or []:
        if isinstance(value, dict):
            tablet_id = as_int(
                value.get('TabletId') or value.get('ColumnShard') or value.get('ShardIdx')
            )
        else:
            tablet_id = as_int(value)
        if tablet_id:
            ids.append(tablet_id)
    return ids


def extract_column_table_tablets(describe):
    path_description = describe.get('PathDescription') or {}
    if 'ColumnTableDescription' not in path_description:
        return None
    sharding = (path_description.get('ColumnTableDescription') or {}).get('Sharding') or {}
    tablets = {}
    for tablet_id in _column_shard_ids(sharding.get('ColumnShards')):
        _add_tablet(tablets, tablet_id, 'columnshard')
    return tablets


def extract_column_store_tablets(describe):
    path_description = describe.get('PathDescription') or {}
    if 'ColumnStoreDescription' not in path_description:
        return None
    description = path_description.get('ColumnStoreDescription') or {}
    tablets = {}
    for tablet_id in _column_shard_ids(description.get('ColumnShards')):
        _add_tablet(tablets, tablet_id, 'columnshard')
    return tablets


EXTRACTORS = {
    'TOPIC': extract_topic_tablets,
    'PERS_QUEUE_GROUP': extract_topic_tablets,
    'TABLE': extract_table_tablets,
    'COLUMN_TABLE': extract_column_table_tablets,
    'COLUMN_STORE': extract_column_store_tablets,
}


def tablets_from_describe(scheme_type, describe):
    """Return ``{tablet_id: {role, parts}}`` or None when the object payload is missing."""
    extractor = EXTRACTORS.get(scheme_type)
    if extractor is None:
        raise ValueError(f'no tablet extractor for scheme type {scheme_type}')
    return extractor(describe)


def _entry_name(entry):
    if not isinstance(entry, dict):
        return ''
    name = entry.get('Name', entry.get('name'))
    return '' if name is None else str(name)


def _entry_type(entry):
    if not isinstance(entry, dict):
        return ''
    if 'PathType' in entry or 'pathType' in entry:
        return scheme_type_name(entry.get('PathType', entry.get('pathType')))
    return scheme_type_name(entry.get('type', entry.get('Type')))


def _entry_subtype(entry):
    if not isinstance(entry, dict):
        return ''
    return scheme_type_name(entry.get('PathSubType', entry.get('pathSubType')))


def _path_description(describe):
    if not isinstance(describe, dict):
        return {}
    return describe.get('PathDescription') or {}


def _table_description(describe):
    return _path_description(describe).get('Table') or {}


def index_type_name(index):
    """Normalize ``TIndexDescription.Type`` to ``GLOBAL``, ``LOCALMINMAX``, ..."""
    if not isinstance(index, dict):
        return ''
    value = index.get('Type', index.get('type'))
    if isinstance(value, bool) or value is None:
        return ''
    if isinstance(value, int) or (isinstance(value, str) and str(value).strip().isdigit()):
        return INDEX_TYPE_BY_NUMBER.get(int(value), '')
    text = str(value).strip()
    if '.' in text:
        text = text.rsplit('.', 1)[-1]
    text = text.upper()
    if text.startswith('EINDEXTYPE'):
        text = text[len('EINDEXTYPE'):]
    return text


def index_may_have_impl_table(index):
    """Local indexes live inside the main table and have no tablets of their own."""
    kind = index_type_name(index)
    if not kind:
        return True
    return kind not in LOCAL_INDEX_TYPES and kind != 'INVALID'


def is_index_impl_child(child):
    child_type = _entry_type(child)
    subtype = _entry_subtype(child)
    return child_type == 'TABLE' or 'INDEXIMPLTABLE' in subtype


def index_impl_paths(index_path, index, index_describe):
    """Implementation-table paths of one secondary index.

    Describe of the index lists them in ``PathDescription.Children``.
    When that listing is absent, use names from ``IndexImplTableDescriptions``
    or the global-index name ``indexImplTable``.
    """
    path_description = _path_description(index_describe)
    if 'Children' in path_description or 'children' in path_description:
        children = path_description.get('Children')
        if children is None:
            children = path_description.get('children') or []
        found = []
        for child in children:
            name = _entry_name(child)
            if not name or not is_index_impl_child(child):
                continue
            found.append(join_path(index_path, name))
        return found

    named = []
    for desc in (index or {}).get('IndexImplTableDescriptions') or []:
        name = _entry_name(desc)
        if name:
            named.append(join_path(index_path, name))
    if named:
        return named
    return [join_path(index_path, INDEX_IMPL_NAME)]


def cdc_stream_paths_from_table(table_path, describe, prefix):
    """CDC changefeed paths declared on a table.

    Schemeshard stores them as children of the table and puts the names in
    ``PathDescription.Table.CdcStreams``. The PersQueue tablets live one level
    deeper, in ``{stream}/streamImpl``.
    """
    table = ((describe or {}).get('PathDescription') or {}).get('Table') or {}
    paths = []
    for stream in table.get('CdcStreams') or []:
        name = _entry_name(stream)
        if not name:
            continue
        stream_path = join_path(table_path, name)
        if paths_intersect(stream_path, prefix):
            paths.append(stream_path)
    return paths


def pq_children_of_stream(stream_path, describe, prefix):
    """PersQueue children of a CDC stream, usually ``streamImpl``.

    When describe does not list children, fall back to the name schemeshard
    uses when it creates the changefeed topic.
    """
    children = ((describe or {}).get('PathDescription') or {}).get('Children') or []
    found = []
    for child in children:
        name = _entry_name(child)
        if not name:
            continue
        child_type = _entry_type(child)
        if (
            child_type not in TOPIC_SCHEME_TYPES
            and _entry_subtype(child) != 'STREAM_IMPL'
            and name != CDC_IMPL_NAME
        ):
            continue
        child_path = join_path(stream_path, name)
        if path_matches_prefix(child_path, prefix):
            found.append(child_path)
    if children:
        return found
    fallback = join_path(stream_path, CDC_IMPL_NAME)
    if path_matches_prefix(fallback, prefix):
        return [fallback]
    return []


def format_detail(rec):
    parts = rec.get('parts') or []
    if not parts:
        return ''
    return ','.join(str(part) for part in sorted(parts))


def normalize_action(name):
    """Return ``stop`` or ``start``. ``resume`` is an alias of ``start``."""
    action = str(name).strip().lower()
    action = ACTION_ALIASES.get(action, action)
    if action not in ACTIONS:
        known = ', '.join(sorted(ACTIONS) + sorted(ACTION_ALIASES))
        raise ValueError(f'unknown action {name!r}; known actions: {known}')
    return action


def parse_hive_response(status_code, text, action):
    """Classify a Hive StopTablet or ResumeTablet HTTP response.

    Returns ``(ok, result)``. Result is the action's done label, its already
    label, ``accepted`` (``--no-wait``), or an error string.
    """
    spec = ACTIONS[action]
    body = text or ''
    if status_code >= 400:
        return False, one_line(f'HTTP {status_code}: {body[:400]}')
    stripped = body.strip()
    if not stripped:
        return False, f'empty response HTTP {status_code}'
    try:
        payload = json.loads(stripped)
    except Exception:
        return False, one_line(f'non-JSON response HTTP {status_code}: {stripped[:400]}')
    if not isinstance(payload, dict):
        return False, one_line(f'unexpected JSON HTTP {status_code}: {stripped[:400]}')
    if payload.get('error'):
        return False, one_line(payload.get('error'))
    status = norm_status(payload.get('Status'))
    if status is None and payload == {}:
        return True, 'accepted'
    if status in ALREADY_STATUSES:
        return True, spec['already']
    if status in SUCCESS_STATUSES:
        return True, spec['done']
    return False, one_line(f'status={payload.get("Status")} body={stripped[:400]}')


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


def list_directory(database, path):
    url = URL_SCHEME_DIRECTORY.format(
        url_base=VIEWER_URL_BASE,
        database=quote(database, safe='/'),
        path=quote(path, safe='/'),
    )
    return load_json(url)


def describe_path(path, extra_query=''):
    url = URL_DESCRIBE.format(
        url_base=VIEWER_URL_BASE,
        path=quote(path, safe='/'),
    )
    if extra_query:
        url = f'{url}&{extra_query}'
    return load_json(url)


def directory_self_type(data):
    self_entry = {}
    if isinstance(data, dict):
        self_entry = data.get('self') or data.get('Self') or {}
    if not isinstance(self_entry, dict):
        return ''
    return scheme_type_name(self_entry.get('type', self_entry.get('Type')))


def resolve_start_path(database, prefix):
    """Deepest directory to walk so a prefix does not scan the whole database."""
    if prefix is None or prefix == database:
        return database

    candidate = prefix
    while True:
        data = None
        try:
            data = list_directory(database, candidate)
        except Exception:
            data = None
        if data is not None and directory_self_type(data) in DIRECTORY_TYPES:
            return candidate
        parent = candidate.rsplit('/', 1)[0]
        if not parent or parent == candidate or len(parent) < len(database):
            return database
        candidate = parent


def iter_children(data):
    if not isinstance(data, dict):
        return []
    children = data.get('children')
    if children is None:
        children = data.get('Children')
    return children or []


def collect_objects(database, start_path, scheme_types, prefix, include_sys):
    """BFS scheme directories; return ``(objects, listing_errors, nested_tables)``.

    ``objects`` is a sorted list of ``(path, scheme_type)``.
    ``listing_errors`` is a list of ``(path, message)`` for directories that
    could not be listed.
    ``nested_tables`` are user tables that may hide secondary-index impl
    tables and CDC changefeed topics.
    """
    objects = []
    listing_errors = []
    nested_tables = []
    queue = [start_path]
    seen_dirs = set()
    want_cdc = bool(TOPIC_SCHEME_TYPES & set(scheme_types))
    want_index_tablets = 'TABLE' in scheme_types
    want_nested = want_cdc or want_index_tablets

    while queue:
        path = queue.pop(0)
        if path in seen_dirs:
            continue
        seen_dirs.add(path)

        try:
            data = list_directory(database, path)
        except Exception as exc:
            message = f'ERROR: {exc}'
            listing_errors.append((path, message))
            log(f'ERROR listing {path}: {exc}')
            continue

        children = iter_children(data)
        log(f'Listed {path}: {len(children)} child(ren)')

        self_type = directory_self_type(data)
        if self_type in scheme_types and path_matches_prefix(path, prefix):
            objects.append((path, self_type))

        for child in children:
            if not isinstance(child, dict):
                continue
            name = child.get('name', child.get('Name'))
            if not name:
                continue
            child_type = scheme_type_name(child.get('type', child.get('Type')))
            child_path = join_path(path, name)

            if child_type in scheme_types and path_matches_prefix(child_path, prefix):
                objects.append((child_path, child_type))

            if want_nested and child_type == 'TABLE' and paths_intersect(child_path, prefix):
                nested_tables.append(child_path)

            if child_type in DIRECTORY_TYPES:
                if not include_sys and str(name).startswith('.'):
                    continue
                # Descend into the prefix itself, its descendants, and its ancestors.
                if (
                    prefix is None
                    or path_matches_prefix(child_path, prefix)
                    or path_matches_prefix(prefix, child_path)
                ):
                    queue.append(child_path)

    objects.sort()
    unique = []
    seen = set()
    for path, scheme_type in objects:
        if path in seen:
            continue
        seen.add(path)
        unique.append((path, scheme_type))
    nested_tables = sorted(set(nested_tables))
    return unique, listing_errors, nested_tables


def cdc_topics_under(owner_path, described, prefix):
    """Return ``(topics, errors)`` for CDC streams declared on ``owner_path``."""
    topics = []
    errors = []
    for stream_path in cdc_stream_paths_from_table(owner_path, described, prefix):
        try:
            stream_described = describe_path(stream_path, CDC_DESCRIBE_QUERY)
        except Exception as exc:
            errors.append((stream_path, f'ERROR: {exc}'))
            continue
        if not describe_is_success(stream_described):
            status = stream_described.get('Status') if isinstance(stream_described, dict) else stream_described
            errors.append((stream_path, f'ERROR: describe status {status}'))
            continue
        for impl_path in pq_children_of_stream(stream_path, stream_described, prefix):
            topics.append((impl_path, 'PERS_QUEUE_GROUP'))
            log(f'CDC topic {impl_path}')
    return topics, errors


def discover_nested_for_table(item):
    """Return ``(objects, errors)`` hidden under one user table.

    ``objects`` contains index implementation tables (scheme type ``TABLE``)
    and changefeed PQ groups (scheme type ``PERS_QUEUE_GROUP``).
    """
    table_path, prefix, want_cdc, want_index_tablets = item
    try:
        described = describe_path(table_path, CDC_DESCRIBE_QUERY)
    except Exception as exc:
        return [], [(table_path, f'ERROR: {exc}')]
    if not describe_is_success(described):
        status = described.get('Status') if isinstance(described, dict) else described
        return [], [(table_path, f'ERROR: describe status {status}')]

    found = []
    errors = []
    if want_cdc:
        topics, topic_errors = cdc_topics_under(table_path, described, prefix)
        found.extend(topics)
        errors.extend(topic_errors)

    for index in _table_description(described).get('TableIndexes') or []:
        if not isinstance(index, dict) or not index_may_have_impl_table(index):
            continue
        name = _entry_name(index)
        if not name:
            continue
        index_path = join_path(table_path, name)
        if not paths_intersect(index_path, prefix):
            continue
        try:
            index_described = describe_path(index_path, CDC_DESCRIBE_QUERY)
        except Exception as exc:
            errors.append((index_path, f'ERROR: {exc}'))
            continue
        if not describe_is_success(index_described):
            status = index_described.get('Status') if isinstance(index_described, dict) else index_described
            errors.append((index_path, f'ERROR: describe status {status}'))
            continue
        for impl_path in index_impl_paths(index_path, index, index_described):
            if want_index_tablets and path_matches_prefix(impl_path, prefix):
                found.append((impl_path, 'TABLE'))
                log(f'Index table {impl_path}')
            if not want_cdc or not paths_intersect(impl_path, prefix):
                continue
            try:
                impl_described = describe_path(impl_path, CDC_DESCRIBE_QUERY)
            except Exception as exc:
                errors.append((impl_path, f'ERROR: {exc}'))
                continue
            if not describe_is_success(impl_described):
                status = impl_described.get('Status') if isinstance(impl_described, dict) else impl_described
                errors.append((impl_path, f'ERROR: describe status {status}'))
                continue
            topics, topic_errors = cdc_topics_under(impl_path, impl_described, prefix)
            found.extend(topics)
            errors.extend(topic_errors)
    return found, errors


def merge_objects(objects, extra):
    seen = {path for path, _scheme_type in objects}
    merged = list(objects)
    for path, scheme_type in extra:
        if path in seen:
            continue
        seen.add(path)
        merged.append((path, scheme_type))
    merged.sort()
    return merged


def collect_tablets_for_object(item):
    path, scheme_type = item
    try:
        described = describe_path(path)
    except Exception as exc:
        return path, scheme_type, None, f'ERROR: {exc}'
    if not describe_is_success(described):
        status = described.get('Status') if isinstance(described, dict) else described
        return path, scheme_type, None, f'ERROR: describe status {status}'
    try:
        tablets = tablets_from_describe(scheme_type, described)
    except Exception as exc:
        return path, scheme_type, None, f'ERROR: {exc}'
    if tablets is None:
        return path, scheme_type, None, 'ERROR: describe has no tablet payload for this object'
    return path, scheme_type, tablets, None


class Target:
    def __init__(self, path, scheme_type, tablet_id, role, detail):
        self.path = path
        self.scheme_type = scheme_type
        self.tablet_id = tablet_id
        self.role = role
        self.detail = detail

    def line(self, result):
        return f'{self.path}\t{self.tablet_id}\t{self.role}\t{self.detail}\t{one_line(result)}'


def targets_from_object(path, scheme_type, tablets):
    result = []
    for tablet_id in sorted(tablets):
        rec = tablets[tablet_id]
        result.append(Target(
            path, scheme_type, tablet_id, rec['role'], format_detail(rec),
        ))
    return result


def dedupe_targets(targets):
    """Keep one operation per tablet id. Later paths are logged and skipped."""
    unique = []
    seen = {}
    for target in targets:
        prev = seen.get(target.tablet_id)
        if prev is None:
            seen[target.tablet_id] = target
            unique.append(target)
            continue
        log(
            f'Skip duplicate tablet {target.tablet_id} at {target.path} '
            f'(already selected for {prev.path})'
        )
    return unique


def hive_tablet_action(action, hive_id, tablet_id, wait):
    """POST StopTablet or ResumeTablet to the Hive monitoring page."""
    params = {
        'TabletID': str(hive_id),
        'page': ACTIONS[action]['page'],
        'tablet': str(tablet_id),
        'wait': 'true' if wait else 'false',
    }
    url = URL_TABLET_APP.format(url_base=VIEWER_URL_BASE)
    response = get_session().post(
        url,
        params=params,
        data=params,
        headers=VIEWER_HEADERS,
        verify=False,
        timeout=HTTP_TIMEOUT,
        allow_redirects=False,
    )
    return parse_hive_response(response.status_code, response.text, action)


def hive_action_with_retries(action, hive_id, tablet_id, wait, attempts):
    last = (False, 'not attempted')
    for attempt in range(1, attempts + 1):
        try:
            ok, result = hive_tablet_action(action, hive_id, tablet_id, wait)
        except Exception as exc:
            ok, result = False, one_line(f'request failed: {exc}')
        last = (ok, result)
        if ok:
            return last
        if 'Tablet not found' in result or 'Must use POST' in result:
            return last
        if attempt >= attempts:
            return last
        delay = RETRY_DELAY_SEC * attempt
        log(
            f'Retry {action} tablet {tablet_id} '
            f'({attempt}/{attempts}): {result}; sleeping {delay:.1f}s'
        )
        time.sleep(delay)
    return last


def main():
    global VIEWER_URL_BASE, HTTP_TIMEOUT

    parser = ArgumentParser(
        formatter_class=RawDescriptionHelpFormatter,
        description=__doc__,
        epilog='''\
Examples:
  %(prog)s --viewer-url https://host:8765 --auth Login /Root/database

  %(prog)s --viewer-url https://host:8765 --auth Login \\
      --path-prefix /Root/database/orders /Root/database

  %(prog)s --action start --viewer-url https://host:8765 --auth Login \\
      --path-prefix /Root/database/orders /Root/database

  %(prog)s --viewer-url https://host:8765 --auth Login \\
      --type TABLE --path-prefix /Root/database/schema1 --dry-run \\
      /Root/database
''',
    )
    parser.add_argument('--viewer-url', required=True)
    parser.add_argument('--auth', dest='auth_mode', default='Login')  # OAuth or Login
    parser.add_argument(
        'database',
        help='Database path used for /scheme/directory and Hive lookup (e.g. /Root/database)',
    )
    parser.add_argument(
        '--action',
        default='stop',
        help=(
            'Hive operation: stop (default) or start. '
            'start sends ResumeTablet and boots tablets that were stopped. '
            'resume is an alias of start'
        ),
    )
    parser.add_argument(
        '--type',
        default='PQ',
        help=(
            'Schema object kind, comma-separated. '
            'Default: PQ (TOPIC, PERS_QUEUE_GROUP, and CDC streamImpl topics, '
            'including changefeeds of secondary indexes). '
            'TABLE also includes DataShard tablets of secondary-index '
            'implementation tables. '
            f'Known: {", ".join(sorted(KIND_SCHEME_TYPES))}'
        ),
    )
    parser.add_argument(
        '--path-prefix',
        default=None,
        help=(
            'Only objects whose path equals this prefix or lies under it. '
            'A relative prefix is resolved under the database path. '
            'Default: the whole database'
        ),
    )
    parser.add_argument(
        '--include-sys',
        action='store_true',
        help='Also walk directories whose names start with "." (e.g. .sys)',
    )
    parser.add_argument(
        '--threads',
        type=int,
        default=4,
        help='Parallel describe and stop/start requests (default: 4)',
    )
    parser.add_argument(
        '--retries',
        type=int,
        default=MAX_ATTEMPTS,
        help=f'Attempts per tablet after a transient error (default: {MAX_ATTEMPTS})',
    )
    parser.add_argument(
        '--timeout',
        type=float,
        default=HTTP_TIMEOUT,
        help=f'HTTP timeout in seconds (default: {HTTP_TIMEOUT})',
    )
    parser.add_argument(
        '--hive-id',
        default=None,
        help='Hive tablet id. Default: read it from the database description',
    )
    parser.add_argument(
        '--no-wait',
        dest='wait',
        action='store_false',
        default=True,
        help='POST the Hive page with wait=false and do not wait for status',
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Print selected tablets without stopping or starting them',
    )
    args = parser.parse_args()

    if args.threads < 1:
        parser.error('--threads must be >= 1')
    if args.retries < 1:
        parser.error('--retries must be >= 1')
    if args.timeout <= 0:
        parser.error('--timeout must be > 0')

    try:
        action = normalize_action(args.action)
    except ValueError as exc:
        parser.error(str(exc))

    try:
        scheme_types, kind_names = parse_kinds(args.type)
    except ValueError as exc:
        parser.error(str(exc))

    database = normalize_path(args.database)
    try:
        prefix = resolve_prefix(database, args.path_prefix)
    except ValueError as exc:
        parser.error(str(exc))

    setup_auth(args.auth_mode)

    VIEWER_URL_BASE = args.viewer_url.rstrip('/')
    HTTP_TIMEOUT = args.timeout

    hive_id = as_int(args.hive_id) if args.hive_id else None
    if args.hive_id and not hive_id:
        parser.error(f'invalid --hive-id {args.hive_id!r}')

    if hive_id is None:
        log(f'Resolving Hive for {database}')
        try:
            hive_id = extract_hive_id(describe_path(database))
        except Exception as exc:
            print(f'Failed to describe {database}: {exc}', file=sys.stderr)
            sys.exit(1)
        if not hive_id and not args.dry_run:
            print(
                f'Hive id not found in describe of {database}. '
                'Pass --hive-id explicitly.',
                file=sys.stderr,
            )
            sys.exit(1)

    log(
        f'Scanning database={database} action={action} type={",".join(kind_names)} '
        f'path_prefix={prefix or database} hive={hive_id or "unknown"}'
    )
    start_path = resolve_start_path(database, prefix)
    log(f'Walking scheme from {start_path}')
    want_cdc = bool(TOPIC_SCHEME_TYPES & set(scheme_types))
    want_index_tablets = 'TABLE' in scheme_types
    objects, listing_errors, nested_tables = collect_objects(
        database, start_path, scheme_types, prefix, include_sys=args.include_sys,
    )
    if nested_tables:
        log(
            f'Checking {len(nested_tables)} table(s) for secondary indexes'
            f'{" and CDC topics" if want_cdc else ""}...'
        )
        nested_objects = []
        checked = 0
        with ThreadPool(min(args.threads, len(nested_tables))) as pool:
            for extra, errors in pool.imap_unordered(
                discover_nested_for_table,
                [
                    (table_path, prefix, want_cdc, want_index_tablets)
                    for table_path in nested_tables
                ],
            ):
                checked += 1
                nested_objects.extend(extra)
                for path, error in errors:
                    listing_errors.append((path, error))
                    log(f'{path}: {error}')
                if checked == len(nested_tables) or checked % 50 == 0:
                    log(
                        f'Nested scan {checked}/{len(nested_tables)} table(s), '
                        f'objects={len(nested_objects)}'
                    )
        objects = merge_objects(objects, nested_objects)
        index_count = sum(1 for _path, kind in nested_objects if kind == 'TABLE')
        log(
            f'Found {index_count} index table(s), '
            f'{len(nested_objects) - index_count} CDC topic(s)'
        )
    log(f'Found {len(objects)} object(s), reading tablets...')

    describe_errors = []
    collected = []
    with ThreadPool(min(args.threads, len(objects) or 1)) as pool:
        for path, scheme_type, tablets, error in pool.imap_unordered(
            collect_tablets_for_object, objects,
        ):
            if error:
                describe_errors.append((path, error))
                log(f'{path}: {error}')
                continue
            object_targets = targets_from_object(path, scheme_type, tablets)
            if not object_targets:
                log(f'{path}: no tablets')
            collected.extend(object_targets)

    collected.sort(key=lambda item: (item.path, item.tablet_id))
    targets = dedupe_targets(collected)
    log(f'Selected {len(targets)} tablet(s) from {len(objects)} object(s)')

    if args.dry_run:
        for target in targets:
            print(target.line('dry-run'), flush=True)
        for path, error in sorted(listing_errors + describe_errors):
            print(f'{path}\t\t\t\t{one_line(error)}', flush=True)
        log(
            f'Dry run: tablets={len(targets)}, '
            f'listing_errors={len(listing_errors)}, '
            f'describe_errors={len(describe_errors)}'
        )
        if listing_errors or describe_errors:
            sys.exit(2)
        return

    if not hive_id:
        print(f'Hive id is required to {action} tablets', file=sys.stderr)
        sys.exit(1)

    progress_lock = threading.Lock()
    progress = {'done': 0, 'errors': 0}

    def process_target(target):
        ok, result = hive_action_with_retries(
            action, hive_id, target.tablet_id, args.wait, args.retries,
        )
        with progress_lock:
            progress['done'] += 1
            if not ok:
                progress['errors'] += 1
            done = progress['done']
            errors = progress['errors']
        log(
            f'[{done}/{len(targets)}] tablet {target.tablet_id} '
            f'{target.path} -> {result} (errors={errors})'
        )
        print(target.line(result if ok else f'error: {result}'), flush=True)
        return ok

    action_errors = 0
    with ThreadPool(min(args.threads, len(targets) or 1)) as pool:
        for ok in pool.imap_unordered(process_target, targets):
            if not ok:
                action_errors += 1

    log(
        f'Done: action={action}, tablets={len(targets)}, '
        f'errors={action_errors}, '
        f'listing_errors={len(listing_errors)}, '
        f'describe_errors={len(describe_errors)}'
    )
    if listing_errors or describe_errors or action_errors:
        sys.exit(2)


if __name__ == '__main__':
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    main()
