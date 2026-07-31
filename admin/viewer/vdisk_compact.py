#!/usr/bin/env python3
"""Trigger VDisk Hull DB compaction via Embedded UI / monitoring pages.

Mirrors `ydb-dstool vdisk compact` (see ydb/apps/dstool/lib/dstool_cmd_vdisk_compact.py):
sends `?type=dbmainpage&dbname=...&action=compact` to the VDisk actor page.

Supports compacting explicit VDisk IDs or all VDisks of a storage pool.
For a pool, groups are processed in parallel while VDisks inside one group
are compacted sequentially.
"""

import os
import re
import sys
import time
import requests
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from collections import defaultdict
from multiprocessing.pool import ThreadPool
from urllib.parse import urlencode

VIEWER_URL_BASE = ''
VIEWER_HEADERS = {}

URL_VDISK_INFO = '{url_base}/viewer/json/vdiskinfo?enums=true'
URL_VDISK_PAGE = (
    '{url_base}/node/{node_id}/actors/vdisks/'
    'vdisk{pdisk_id:09d}_{vslot_id:09d}'
)

RE_VDISK_BRACKET = re.compile(
    r'^\[([0-9a-fA-F]+):(?:_|(\d+)):(\d+):(\d+):(\d+)\]$'
)
RE_VDISK_PAREN = re.compile(r'^\((\d+)-(\d+)-(\d+)-(\d+)-(\d+)\)$')
RE_COMPACTION_IN_PROGRESS = re.compile(r'In progress', re.I)
RE_COMPACTION_IDLE = re.compile(r'No compaction', re.I)


def load_json(url):
    response = requests.get(url, headers=VIEWER_HEADERS, verify=False, timeout=120)
    response.raise_for_status()
    return response.json()


def http_get(url, allow_redirects=True):
    response = requests.get(
        url,
        headers=VIEWER_HEADERS,
        verify=False,
        timeout=120,
        allow_redirects=allow_redirects,
    )
    return response


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


def resolve_dbnames(args):
    if args.full:
        return ['LogoBlobs', 'Blocks', 'Barriers']

    dbnames = []
    if args.compact_logoblobs:
        dbnames.append('LogoBlobs')
    if args.compact_blocks:
        dbnames.append('Blocks')
    if args.compact_barriers:
        dbnames.append('Barriers')
    if not dbnames:
        dbnames = ['LogoBlobs']
    return dbnames


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


def compaction_state(vdisk, dbname):
    url = vdisk_page_url(vdisk, dbname=dbname)
    text = http_get(url).text
    if RE_COMPACTION_IN_PROGRESS.search(text):
        return 'In progress'
    if RE_COMPACTION_IDLE.search(text):
        return 'No compaction'
    return 'Unknown'


def start_compaction(vdisk, dbname):
    url = vdisk_page_url(vdisk, dbname=dbname, action='compact')
    # dstool ignores the redirect body; follow redirects for simplicity.
    response = http_get(url, allow_redirects=True)
    if response.status_code >= 400:
        raise Exception(
            f'HTTP {response.status_code} while compacting '
            f'{vdisk["vdisk_id"]} {dbname}'
        )


def wait_compaction(vdisk, dbname, poll_interval):
    while True:
        state = compaction_state(vdisk, dbname)
        if state != 'In progress':
            return state
        time.sleep(poll_interval)


def compact_vdisk(vdisk, dbnames, wait, poll_interval, dry_run):
    for dbname in dbnames:
        page = vdisk_page_url(vdisk, dbname=dbname, action='compact')
        print(
            f'[{time.ctime()}] Compact {vdisk["vdisk_id"]} '
            f'group={vdisk["group_id"]} db={dbname} '
            f'node={vdisk["node_id"]} pdisk={vdisk["pdisk_id"]} '
            f'vslot={vdisk["vslot_id"]} url={page}'
        )
        if dry_run:
            continue
        start_compaction(vdisk, dbname)
        if wait:
            state = wait_compaction(vdisk, dbname, poll_interval)
            print(
                f'[{time.ctime()}] Done {vdisk["vdisk_id"]} '
                f'db={dbname} state={state}'
            )


def compact_group(task):
    group_id, vdisks, dbnames, wait, poll_interval, dry_run = task
    errors = []
    print(
        f'[{time.ctime()}] Group {group_id}: '
        f'start ({len(vdisks)} VDisk(s), sequential)'
    )
    for vdisk in sorted(
        vdisks,
        key=lambda v: (v['fail_realm'], v['fail_domain'], v['vdisk_idx'], v['vdisk_id']),
    ):
        try:
            compact_vdisk(vdisk, dbnames, wait, poll_interval, dry_run)
        except Exception as exc:
            msg = f'{vdisk["vdisk_id"]}: {exc}'
            print(f'[{time.ctime()}] ERROR {msg}', file=sys.stderr)
            errors.append(msg)
    print(f'[{time.ctime()}] Group {group_id}: finished')
    return group_id, errors


def run_pool_compaction(vdisks, dbnames, threads, wait, poll_interval, dry_run):
    by_group = defaultdict(list)
    for vdisk in vdisks:
        by_group[vdisk['group_id']].append(vdisk)

    group_ids = sorted(by_group)
    print(
        f'[{time.ctime()}] Pool compaction: {len(vdisks)} VDisk(s) '
        f'in {len(group_ids)} group(s), threads={threads}, wait={wait}'
    )

    tasks = [
        (group_id, by_group[group_id], dbnames, wait, poll_interval, dry_run)
        for group_id in group_ids
    ]

    all_errors = []
    with ThreadPool(threads) as pool:
        for group_id, errors in pool.imap_unordered(compact_group, tasks):
            all_errors.extend(errors)
            if errors:
                print(
                    f'[{time.ctime()}] Group {group_id}: '
                    f'{len(errors)} error(s)'
                )
    return all_errors


def main():
    parser = ArgumentParser(
        formatter_class=RawDescriptionHelpFormatter,
        description=__doc__,
        epilog='''\
Examples:
  %(prog)s --viewer-url https://host:8765 --auth Login --full \\
      --vdisk-ids '[00000001:1:0:0:0]'

  %(prog)s --viewer-url https://host:8765 --auth Login --full \\
      --pool /Root:ssd --threads 8
''',
    )
    parser.add_argument('--viewer-url', required=True)
    parser.add_argument('--auth', dest='auth_mode', default='Login')  # OAuth or Login
    parser.add_argument('--threads', type=int, default=8,
                        help='Max storage groups compacted in parallel (pool mode)')
    parser.add_argument('--full', action='store_true',
                        help='Compact LogoBlobs, Blocks and Barriers')
    parser.add_argument('--compact-logoblobs', action='store_true',
                        help='Compact LogoBlobs')
    parser.add_argument('--compact-blocks', action='store_true',
                        help='Compact Blocks')
    parser.add_argument('--compact-barriers', action='store_true',
                        help='Compact Barriers')
    parser.add_argument('--vdisk-ids', type=str, nargs='+',
                        help='Space-separated VDisk ids (dstool formats)')
    parser.add_argument('--pool', type=str,
                        help='Storage pool name; compact all its VDisks')
    parser.add_argument('--wait', dest='wait', action='store_true', default=True,
                        help='Wait until compaction finishes (default)')
    parser.add_argument('--no-wait', dest='wait', action='store_false',
                        help='Do not wait for compaction to finish')
    parser.add_argument('--poll-interval', type=float, default=5.0,
                        help='Seconds between compaction status polls')
    parser.add_argument('--dry-run', action='store_true',
                        help='Only list target VDisks / URLs')
    args = parser.parse_args()

    if bool(args.vdisk_ids) == bool(args.pool):
        parser.error('Specify exactly one of --vdisk-ids or --pool')
    if args.threads < 1:
        parser.error('--threads must be >= 1')

    setup_auth(args.auth_mode)

    global VIEWER_URL_BASE
    VIEWER_URL_BASE = args.viewer_url.rstrip('/')

    dbnames = resolve_dbnames(args)
    vdisks = fetch_vdisks()

    if args.pool:
        selected = select_pool_vdisks(args.pool, vdisks)
        errors = run_pool_compaction(
            selected, dbnames, args.threads, args.wait,
            args.poll_interval, args.dry_run,
        )
    else:
        selected = resolve_vdisk_ids(args.vdisk_ids, vdisks)
        errors = []
        # Keep dstool-like ordering for explicit ids, but still serialize
        # VDisks that share a storage group when waiting.
        if args.wait:
            by_group = defaultdict(list)
            order = []
            for v in selected:
                if v['group_id'] not in by_group:
                    order.append(v['group_id'])
                by_group[v['group_id']].append(v)
            tasks = [
                (group_id, by_group[group_id], dbnames, args.wait,
                 args.poll_interval, args.dry_run)
                for group_id in order
            ]
            with ThreadPool(min(args.threads, len(tasks) or 1)) as pool:
                for _, group_errors in pool.imap_unordered(compact_group, tasks):
                    errors.extend(group_errors)
        else:
            for vdisk in selected:
                try:
                    compact_vdisk(
                        vdisk, dbnames, args.wait,
                        args.poll_interval, args.dry_run,
                    )
                except Exception as exc:
                    msg = f'{vdisk["vdisk_id"]}: {exc}'
                    print(f'[{time.ctime()}] ERROR {msg}', file=sys.stderr)
                    errors.append(msg)

    if errors:
        print(f'Failed for {len(errors)} VDisk operation(s)', file=sys.stderr)
        sys.exit(1)
    print(f'[{time.ctime()}] Successfully processed {len(selected)} VDisk(s)')


if __name__ == '__main__':
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    main()
