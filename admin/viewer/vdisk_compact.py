#!/usr/bin/env python3
"""Trigger VDisk Hull DB compaction / defrag via Embedded UI monitoring pages.

Mirrors `ydb-dstool vdisk compact` (see ydb/apps/dstool/lib/dstool_cmd_vdisk_compact.py):
sends `?type=dbmainpage&dbname=...&action=compact` to the VDisk actor page.

Mode `defrag` separately triggers LogoBlobs defrag (`action=defrag`).

Supports operating on explicit VDisk IDs or all VDisks of a storage pool.
For a pool, groups are processed in parallel while VDisks inside one group
are processed sequentially.
"""

import os
import re
import sys
import time
import threading
import requests
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from collections import defaultdict
from multiprocessing.pool import ThreadPool
from urllib.parse import urlencode

VIEWER_URL_BASE = ''
VIEWER_HEADERS = {}
DEBUG = False

URL_VDISK_INFO = '{url_base}/viewer/json/vdiskinfo?enums=true'
URL_VDISK_PAGE = (
    '{url_base}/node/{node_id}/actors/vdisks/'
    'vdisk{pdisk_id:09d}_{vslot_id:09d}'
)

RE_VDISK_BRACKET = re.compile(
    r'^\[([0-9a-fA-F]+):(?:_|(\d+)):(\d+):(\d+):(\d+)\]$'
)
RE_VDISK_PAREN = re.compile(r'^\((\d+)-(\d+)-(\d+)-(\d+)-(\d+)\)$')
# LogoBlobs dbmainpage renders both Full Compaction and Defrag panels;
# each has its own "In progress" label — parse panels separately.
RE_COMPACTION_PANEL = re.compile(
    r'Database Full Compaction(?P<body>.*?)(?:Database Defrag|\Z)',
    re.I | re.S,
)
RE_DEFRAG_PANEL = re.compile(
    r'Database Defrag(?P<body>.*?)(?:</div>\s*</div>\s*\Z|\Z)',
    re.I | re.S,
)
RE_COMPACTION_STATE = re.compile(
    r'>\s*(In progress|No compaction)\s*<',
    re.I,
)
RE_DEFRAG_STATE = re.compile(
    r'>\s*(In progress|No defrag)\s*<',
    re.I,
)

HTTP_TIMEOUT = 30
SESSION = None

MODE_COMPACT_FULL = 'compact-full'
MODE_COMPACT_LOGOBLOBS = 'compact-logoblobs'
MODE_COMPACT_BLOCKS = 'compact-blocks'
MODE_COMPACT_BARRIERS = 'compact-barriers'
MODE_DEFRAG = 'defrag'
MODES = (
    MODE_COMPACT_FULL,
    MODE_COMPACT_LOGOBLOBS,
    MODE_COMPACT_BLOCKS,
    MODE_COMPACT_BARRIERS,
    MODE_DEFRAG,
)


def log(msg, file=sys.stdout):
    print(f'[{time.ctime()}] {msg}', file=file, flush=True)


def debug_log(msg, file=sys.stdout):
    if DEBUG:
        log(msg, file=file)


def vdisk_sort_key(vdisk):
    return (
        vdisk['group_id'],
        vdisk['fail_realm'],
        vdisk['fail_domain'],
        vdisk['vdisk_idx'],
        vdisk['vdisk_id'],
    )


def sort_vdisks(vdisks):
    return sorted(vdisks, key=vdisk_sort_key)


class Progress:
    def __init__(self, total):
        self.total = total
        self.done = 0
        self.errors = 0
        self._lock = threading.Lock()

    def _line(self):
        remaining = self.total - self.done
        pct = 100.0 * self.done / self.total if self.total else 100.0
        return (
            f'Progress: done={self.done}/{self.total} ({pct:.1f}%), '
            f'remaining={remaining}, errors={self.errors}'
        )

    def report(self):
        log(self._line())

    def mark_done(self, ok=True):
        with self._lock:
            self.done += 1
            if not ok:
                self.errors += 1
            self.report()


def get_session():
    global SESSION
    if SESSION is None:
        SESSION = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=32,
            pool_maxsize=32,
            max_retries=0,
        )
        SESSION.mount('http://', adapter)
        SESSION.mount('https://', adapter)
    return SESSION


def load_json(url):
    response = get_session().get(
        url, headers=VIEWER_HEADERS, verify=False, timeout=HTTP_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def http_get(url, allow_redirects=True):
    return get_session().get(
        url,
        headers=VIEWER_HEADERS,
        verify=False,
        timeout=HTTP_TIMEOUT,
        allow_redirects=allow_redirects,
    )


def setup_auth(auth_mode):
    global VIEWER_HEADERS
    if auth_mode == '' or auth_mode.lower() == 'disabled':
        VIEWER_HEADERS = {}
        return

    token_path = os.path.expanduser('~/.ydb/token')
    if not os.path.isfile(token_path):
        print(f'{token_path} does not exist')
        sys.exit(1)

    token = open(token_path).read().strip()
    VIEWER_HEADERS = {
        'Authorization': f'{auth_mode} {token}',
    }


def resolve_mode(mode):
    """Return (dbnames, do_defrag) for the selected --mode."""
    if mode == MODE_COMPACT_FULL:
        return ['LogoBlobs', 'Blocks', 'Barriers'], False
    if mode == MODE_COMPACT_LOGOBLOBS:
        return ['LogoBlobs'], False
    if mode == MODE_COMPACT_BLOCKS:
        return ['Blocks'], False
    if mode == MODE_COMPACT_BARRIERS:
        return ['Barriers'], False
    if mode == MODE_DEFRAG:
        return [], True
    raise ValueError(f'Unsupported mode: {mode}')


def parse_vdisk_id(vdisk_id):
    """Parse dstool-compatible VDisk id formats.

    Supported:
      [GroupId(hex):_:FailRealm:FailDomain:VDiskIdx]
      [GroupId(hex):GroupGen:FailRealm:FailDomain:VDiskIdx]
      (GroupId(dec)-GroupGen-FailRealm-FailDomain-VDiskIdx)
    """
    m = RE_VDISK_BRACKET.match(vdisk_id)
    if m:
        group_id = int(m.group(1), 16)
        group_gen = int(m.group(2)) if m.group(2) is not None else None
        return group_id, group_gen, int(m.group(3)), int(m.group(4)), int(m.group(5))

    m = RE_VDISK_PAREN.match(vdisk_id)
    if m:
        return (
            int(m.group(1)),
            int(m.group(2)),
            int(m.group(3)),
            int(m.group(4)),
            int(m.group(5)),
        )

    raise ValueError(f'Unsupported VDisk id format: {vdisk_id}')


def format_vdisk_id(group_id, group_gen, fail_realm, fail_domain, vdisk_idx):
    return '[%08x:%u:%u:%u:%u]' % (
        group_id, group_gen, fail_realm, fail_domain, vdisk_idx
    )


def extract_vdisk_fields(item):
    vdisk_id = item.get('VDiskId') or {}
    group_id = int(vdisk_id.get('GroupID', vdisk_id.get('GroupId', 0)))
    group_gen = int(vdisk_id.get('GroupGeneration', 0))
    fail_realm = int(vdisk_id.get('Ring', vdisk_id.get('FailRealm', 0)))
    fail_domain = int(vdisk_id.get('Domain', vdisk_id.get('FailDomain', 0)))
    vdisk_idx = int(vdisk_id.get('VDisk', vdisk_id.get('VDiskIdx', 0)))
    node_id = int(item.get('NodeId', 0))
    pdisk_id = int(item.get('PDiskId', 0))
    vslot_id = int(item.get('VDiskSlotId', item.get('VSlotId', 0)))
    pool_name = item.get('StoragePoolName') or ''
    return {
        'group_id': group_id,
        'group_gen': group_gen,
        'fail_realm': fail_realm,
        'fail_domain': fail_domain,
        'vdisk_idx': vdisk_idx,
        'node_id': node_id,
        'pdisk_id': pdisk_id,
        'vslot_id': vslot_id,
        'pool_name': pool_name,
        'vdisk_id': format_vdisk_id(
            group_id, group_gen, fail_realm, fail_domain, vdisk_idx
        ),
    }


def fetch_vdisks():
    data = load_json(URL_VDISK_INFO.format(url_base=VIEWER_URL_BASE))
    items = data.get('VDiskStateInfo') or []
    # When querying a single node, viewer may wrap response under node id keys.
    if not items and isinstance(data, dict):
        merged = []
        for value in data.values():
            if isinstance(value, dict) and 'VDiskStateInfo' in value:
                merged.extend(value['VDiskStateInfo'])
        items = merged

    vdisks = []
    for item in items:
        fields = extract_vdisk_fields(item)
        if not fields['node_id'] or not fields['pdisk_id']:
            continue
        vdisks.append(fields)
    return vdisks


def build_vdisk_indexes(vdisks):
    by_full = {}
    by_short = {}
    for v in vdisks:
        by_full[v['vdisk_id']] = v
        short = '[%08x:_:%u:%u:%u]' % (
            v['group_id'], v['fail_realm'], v['fail_domain'], v['vdisk_idx']
        )
        # Prefer higher generation when several slots match the short id.
        prev = by_short.get(short)
        if prev is None or v['group_gen'] >= prev['group_gen']:
            by_short[short] = v
        paren = '(%d-%u-%u-%u-%u)' % (
            v['group_id'], v['group_gen'], v['fail_realm'],
            v['fail_domain'], v['vdisk_idx']
        )
        by_full[paren] = v
    return by_full, by_short


def resolve_vdisk_ids(vdisk_ids, vdisks):
    by_full, by_short = build_vdisk_indexes(vdisks)
    resolved = []
    for chunk in vdisk_ids:
        for vdisk_id in chunk.split():
            parse_vdisk_id(vdisk_id)  # validate format early
            v = by_full.get(vdisk_id) or by_short.get(vdisk_id)
            if v is None:
                # Normalize bracket form with generation for lookup.
                group_id, group_gen, fr, fd, vi = parse_vdisk_id(vdisk_id)
                if group_gen is None:
                    key = '[%08x:_:%u:%u:%u]' % (group_id, fr, fd, vi)
                    v = by_short.get(key)
                else:
                    key = format_vdisk_id(group_id, group_gen, fr, fd, vi)
                    v = by_full.get(key)
            if v is None:
                raise Exception(f'VDisk with id {vdisk_id} not found')
            resolved.append(v)
    return resolved


def select_pool_vdisks(pool_name, vdisks):
    selected = [v for v in vdisks if v['pool_name'] == pool_name]
    if not selected:
        available = sorted({v['pool_name'] for v in vdisks if v['pool_name']})
        hint = ', '.join(available[:20]) if available else '(none)'
        raise Exception(
            f'No VDisks found for storage pool {pool_name!r}. '
            f'Known pools: {hint}'
        )
    return selected


def vdisk_page_url(vdisk, dbname=None, action=None):
    url = URL_VDISK_PAGE.format(
        url_base=VIEWER_URL_BASE,
        node_id=vdisk['node_id'],
        pdisk_id=vdisk['pdisk_id'],
        vslot_id=vdisk['vslot_id'],
    )
    params = {'type': 'dbmainpage'}
    if dbname is not None:
        params['dbname'] = dbname
    if action is not None:
        params['action'] = action
    return f'{url}?{urlencode(params)}'


def parse_panel_state(text, panel_re, state_re, idle_literal, in_progress_literal='In progress'):
    panel = panel_re.search(text)
    chunk = panel.group('body') if panel else text
    match = state_re.search(chunk)
    if match:
        value = match.group(1)
        if value.lower() == in_progress_literal.lower():
            return 'In progress'
        return idle_literal
    if re.search(re.escape(idle_literal), chunk, re.I):
        return idle_literal
    if re.search(re.escape(in_progress_literal), chunk, re.I):
        return 'In progress'
    return 'Unknown'


def parse_compaction_state(text):
    """Return Full Compaction state, ignoring Database Defrag panel."""
    return parse_panel_state(
        text, RE_COMPACTION_PANEL, RE_COMPACTION_STATE, 'No compaction',
    )


def parse_defrag_state(text):
    """Return Database Defrag state, ignoring Full Compaction panel."""
    return parse_panel_state(
        text, RE_DEFRAG_PANEL, RE_DEFRAG_STATE, 'No defrag',
    )


def fetch_dbmainpage(vdisk, dbname='LogoBlobs'):
    url = vdisk_page_url(vdisk, dbname=dbname)
    response = http_get(url)
    response.raise_for_status()
    return response.text


def compaction_state(vdisk, dbname):
    return parse_compaction_state(fetch_dbmainpage(vdisk, dbname))


def defrag_state(vdisk):
    return parse_defrag_state(fetch_dbmainpage(vdisk, 'LogoBlobs'))


def start_vdisk_action(vdisk, dbname, action):
    url = vdisk_page_url(vdisk, dbname=dbname, action=action)
    # Do not follow the 303 redirect to the heavy status page.
    response = http_get(url, allow_redirects=False)
    if response.status_code >= 400:
        raise Exception(
            f'HTTP {response.status_code} while {action} '
            f'{vdisk["vdisk_id"]} {dbname}'
        )


def start_compaction(vdisk, dbname):
    start_vdisk_action(vdisk, dbname, 'compact')


def start_defrag(vdisk):
    # Defrag is supported only for LogoBlobs on the mon page.
    start_vdisk_action(vdisk, 'LogoBlobs', 'defrag')


def wait_until_idle(vdisk, label, state_fn, poll_interval):
    started = time.time()
    saw_in_progress = False
    # Request is async; give it a moment to appear in status.
    deadline_to_appear = started + max(poll_interval, 5.0)

    while True:
        try:
            state = state_fn()
        except Exception as exc:
            debug_log(
                f'Wait {vdisk["vdisk_id"]} {label}: '
                f'status poll failed: {exc}; retrying'
            )
            time.sleep(poll_interval)
            continue

        if state == 'In progress':
            saw_in_progress = True
            elapsed = int(time.time() - started)
            debug_log(
                f'Wait {vdisk["vdisk_id"]} {label}: '
                f'In progress ({elapsed}s)'
            )
            time.sleep(poll_interval)
            continue

        if saw_in_progress or time.time() >= deadline_to_appear:
            return state

        # Operation not visible yet — keep polling briefly.
        time.sleep(min(poll_interval, 1.0))


def wait_compaction(vdisk, dbname, poll_interval):
    return wait_until_idle(
        vdisk,
        f'db={dbname}',
        lambda: compaction_state(vdisk, dbname),
        poll_interval,
    )


def wait_defrag(vdisk, poll_interval):
    return wait_until_idle(
        vdisk,
        'defrag',
        lambda: defrag_state(vdisk),
        poll_interval,
    )


def process_vdisk(vdisk, dbnames, wait, poll_interval, dry_run, do_defrag=False):
    if do_defrag:
        page = vdisk_page_url(vdisk, dbname='LogoBlobs', action='defrag')
        debug_log(
            f'Defrag {vdisk["vdisk_id"]} '
            f'group={vdisk["group_id"]} db=LogoBlobs '
            f'node={vdisk["node_id"]} pdisk={vdisk["pdisk_id"]} '
            f'vslot={vdisk["vslot_id"]} url={page}'
        )
        if dry_run:
            return
        start_defrag(vdisk)
        if wait:
            state = wait_defrag(vdisk, poll_interval)
            debug_log(f'Done defrag {vdisk["vdisk_id"]} state={state}')
        return

    for dbname in dbnames:
        page = vdisk_page_url(vdisk, dbname=dbname, action='compact')
        debug_log(
            f'Compact {vdisk["vdisk_id"]} '
            f'group={vdisk["group_id"]} db={dbname} '
            f'node={vdisk["node_id"]} pdisk={vdisk["pdisk_id"]} '
            f'vslot={vdisk["vslot_id"]} url={page}'
        )
        if dry_run:
            continue
        start_compaction(vdisk, dbname)
        if wait:
            state = wait_compaction(vdisk, dbname, poll_interval)
            debug_log(
                f'Done compact {vdisk["vdisk_id"]} db={dbname} state={state}'
            )


def process_group(task):
    (
        group_id, vdisks, dbnames, wait, poll_interval, dry_run,
        do_defrag, progress,
    ) = task
    errors = []
    debug_log(f'Group {group_id}: start ({len(vdisks)} VDisk(s), sequential)')
    for vdisk in vdisks:
        try:
            process_vdisk(
                vdisk, dbnames, wait, poll_interval, dry_run, do_defrag=do_defrag,
            )
            progress.mark_done(ok=True)
        except Exception as exc:
            msg = f'{vdisk["vdisk_id"]}: {exc}'
            log(f'ERROR {msg}', file=sys.stderr)
            errors.append(msg)
            progress.mark_done(ok=False)
    debug_log(f'Group {group_id}: finished')
    return group_id, errors


def group_vdisks(vdisks):
    """Group already-sorted VDisks, preserving group order and in-group order."""
    by_group = defaultdict(list)
    group_ids = []
    for vdisk in vdisks:
        group_id = vdisk['group_id']
        if group_id not in by_group:
            group_ids.append(group_id)
        by_group[group_id].append(vdisk)
    return group_ids, by_group


def run_operations(vdisks, mode, dbnames, threads, wait, poll_interval, dry_run,
                   do_defrag=False):
    vdisks = sort_vdisks(vdisks)
    group_ids, by_group = group_vdisks(vdisks)
    progress = Progress(len(vdisks))
    log(
        f'Starting: mode={mode}, {len(vdisks)} VDisk(s) in {len(group_ids)} '
        f'group(s), threads={threads}, wait={wait}, dry_run={dry_run}'
    )
    progress.report()

    tasks = [
        (
            group_id, by_group[group_id], dbnames, wait, poll_interval, dry_run,
            do_defrag, progress,
        )
        for group_id in group_ids
    ]

    all_errors = []
    with ThreadPool(min(threads, len(tasks) or 1)) as pool:
        for group_id, errors in pool.imap_unordered(process_group, tasks):
            all_errors.extend(errors)
            if errors:
                debug_log(f'Group {group_id}: {len(errors)} error(s)')
    return all_errors


def main():
    parser = ArgumentParser(
        formatter_class=RawDescriptionHelpFormatter,
        description=__doc__,
        epilog='''\
Examples:
  %(prog)s --viewer-url https://host:8765 --auth Login \\
      --mode compact-full --vdisk-ids '[00000001:1:0:0:0]'

  %(prog)s --viewer-url https://host:8765 --auth Login \\
      --mode compact-full --pool /Root:ssd --threads 8

  %(prog)s --viewer-url https://host:8765 --auth Login \\
      --mode defrag --pool /Root:ssd --threads 8
''',
    )
    parser.add_argument('--viewer-url', required=True)
    parser.add_argument('--auth', dest='auth_mode', default='Login')  # OAuth or Login
    parser.add_argument('--threads', type=int, default=8,
                        help='Max storage groups processed in parallel (pool mode)')
    parser.add_argument(
        '--mode',
        choices=MODES,
        default=MODE_COMPACT_FULL,
        help=(
            'Operation mode: compact-full (LogoBlobs+Blocks+Barriers, default), '
            'compact-logoblobs, compact-blocks, compact-barriers, or defrag'
        ),
    )
    parser.add_argument('--vdisk-ids', type=str, nargs='+',
                        help='Space-separated VDisk ids (dstool formats)')
    parser.add_argument('--pool', type=str,
                        help='Storage pool name; process all its VDisks')
    parser.add_argument('--wait', dest='wait', action='store_true', default=True,
                        help='Wait until operation finishes (default)')
    parser.add_argument('--no-wait', dest='wait', action='store_false',
                        help='Do not wait for operation to finish')
    parser.add_argument('--poll-interval', type=float, default=5.0,
                        help='Seconds between status polls')
    parser.add_argument('--dry-run', action='store_true',
                        help='Only list target VDisks / URLs')
    parser.add_argument('--debug', action='store_true',
                        help='Print per-VDisk / wait debug details')
    args = parser.parse_args()

    if bool(args.vdisk_ids) == bool(args.pool):
        parser.error('Specify exactly one of --vdisk-ids or --pool')
    if args.threads < 1:
        parser.error('--threads must be >= 1')

    global DEBUG
    DEBUG = bool(args.debug)

    setup_auth(args.auth_mode)

    global VIEWER_URL_BASE
    VIEWER_URL_BASE = args.viewer_url.rstrip('/')

    dbnames, do_defrag = resolve_mode(args.mode)
    vdisks = fetch_vdisks()

    if args.pool:
        selected = sort_vdisks(select_pool_vdisks(args.pool, vdisks))
    else:
        selected = sort_vdisks(resolve_vdisk_ids(args.vdisk_ids, vdisks))

    errors = run_operations(
        selected, args.mode, dbnames, args.threads, args.wait,
        args.poll_interval, args.dry_run, do_defrag=do_defrag,
    )

    if errors:
        log(f'Failed for {len(errors)} VDisk operation(s)', file=sys.stderr)
        sys.exit(1)
    log(f'Successfully processed {len(selected)} VDisk(s)')


if __name__ == '__main__':
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    main()
