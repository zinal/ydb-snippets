#!/usr/bin/env python3
import os
import random
import re
import subprocess
import sys
import threading
import time
import requests
from argparse import ArgumentParser
from urllib.parse import quote_plus


VIEWER_URL_BASE = ''
VIEWER_HEADERS = {}
MAX_RETRIES = 10
TOKEN_AUTH = None

URL_TABLE_DESCRIPTION = '{url_base}/viewer/json/describe?path={path}&enums=true'
URL_EXECUTOR_INTERNALS = '{url_base}/tablets/executorInternals?TabletID={tablet_id}'
URL_FORCE_COMPACT = '{url_base}/tablets/executorInternals?TabletID={tablet_id}&force_compaction={local_table_id}'
RE_DBASE_SIZE = re.compile(r'DBase{.*?, (\d+)\)b}', re.S)
RE_LOANED_PARTS = re.compile(r'<h4>Loaned parts</h4><pre>(.*?)</pre>', re.S)
RE_FORCED_COMPACTION_STATE = re.compile(r'Forced compaction: (\w+)', re.S)

# Transient viewer/tablet errors that usually clear after a short pause.
RETRYABLE_ERROR_MARKERS = (
    'is not connected with status: ERROR',
    'ERROR: cannot compact the specified table',
)

TOKEN_MAX_AGE_SEC = 5 * 60
GET_TOKEN_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'get_token.py')
DEFAULT_TOKEN_PATH = os.path.expanduser('~/.ydb/token')


def token_file_is_fresh(path, max_age_sec=TOKEN_MAX_AGE_SEC):
    try:
        st = os.stat(path)
    except FileNotFoundError:
        return False
    if st.st_size == 0:
        return False
    return (time.time() - st.st_mtime) < max_age_sec


def read_token_file(token_path):
    if not os.path.isfile(token_path):
        raise RuntimeError(f'{token_path} does not exist')
    token = open(token_path).read().strip()
    if not token:
        raise RuntimeError(f'{token_path} is empty')
    return token


def run_get_token(viewer_url, token_path):
    if not os.path.isfile(GET_TOKEN_SCRIPT):
        raise RuntimeError(f'{GET_TOKEN_SCRIPT} does not exist')
    print(f'[{time.ctime()}] Refreshing token via {GET_TOKEN_SCRIPT}')
    result = subprocess.run(
        [
            sys.executable,
            GET_TOKEN_SCRIPT,
            '--viewer-url', viewer_url,
            '--token-path', token_path,
        ],
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f'{GET_TOKEN_SCRIPT} failed with exit code {result.returncode}'
        )


class TokenAuth:
    """Keep Authorization header fresh when --auto-login is enabled."""

    def __init__(self, auth_mode, token_path, viewer_url, auto_login=False):
        self.auth_mode = auth_mode
        self.token_path = token_path
        self.viewer_url = viewer_url
        self.auto_login = auto_login
        self._lock = threading.Lock()
        self._loaded_at = 0.0
        self._apply_token(read_token_file(self.token_path))

    def _apply_token(self, token):
        global VIEWER_HEADERS
        VIEWER_HEADERS = {
            'Authorization': f'{self.auth_mode} {token}',
        }
        self._loaded_at = time.time()

    def ensure_fresh(self):
        if not self.auto_login:
            return
        if (time.time() - self._loaded_at) < TOKEN_MAX_AGE_SEC:
            return

        with self._lock:
            if (time.time() - self._loaded_at) < TOKEN_MAX_AGE_SEC:
                return

            try:
                if token_file_is_fresh(self.token_path):
                    print(
                        f'[{time.ctime()}] Reloading fresh token from {self.token_path}'
                    )
                    self._apply_token(read_token_file(self.token_path))
                    return

                run_get_token(self.viewer_url, self.token_path)
                self._apply_token(read_token_file(self.token_path))
            except RuntimeError as e:
                print(str(e), file=sys.stderr)
                sys.stderr.flush()
                # Worker threads ignore SystemExit; abort the whole process.
                os._exit(1)


def is_retryable_error(text):
    return any(marker in text for marker in RETRYABLE_ERROR_MARKERS)


def viewer_get_text(url):
    """GET text from viewer, retrying known transient tablet errors."""
    attempt = 0
    while True:
        if TOKEN_AUTH is not None:
            TOKEN_AUTH.ensure_fresh()
        text = requests.get(url, headers=VIEWER_HEADERS, verify=False).text
        if not is_retryable_error(text):
            return text

        attempt += 1
        if attempt > MAX_RETRIES:
            raise RuntimeError(
                f'Retryable viewer error after {MAX_RETRIES} retries for {url}:\n{text}'
            )

        delay = random.uniform(1, 5)
        print(
            f'[{time.ctime()}] Retryable error (attempt {attempt}/{MAX_RETRIES}), '
            f'sleeping {delay:.2f}s; url: {url}'
        )
        time.sleep(delay)


def load_json(url):
    if TOKEN_AUTH is not None:
        TOKEN_AUTH.ensure_fresh()
    return requests.get(url, headers=VIEWER_HEADERS, verify=False).json()


def describe_table(path):
    url = URL_TABLE_DESCRIPTION.format(url_base=VIEWER_URL_BASE, path=quote_plus(path))
    return load_json(url)


def tablet_internals(tablet_id):
    url = URL_EXECUTOR_INTERNALS.format(url_base=VIEWER_URL_BASE, tablet_id=tablet_id)
    return viewer_get_text(url)


def extract_loaned_parts(text):
    m = RE_LOANED_PARTS.search(text)
    if m:
        return m.group(1).split()
    else:
        return None


def extract_force_compaction_state(text):
    m = RE_FORCED_COMPACTION_STATE.search(text)
    if m:
        return m.group(1)
    else:
        return None


def start_force_compaction(tablet_id, local_table_id=1001):
    url = URL_FORCE_COMPACT.format(url_base=VIEWER_URL_BASE, tablet_id=tablet_id, local_table_id=local_table_id)
    text = viewer_get_text(url)
    if 'Table will be compacted in the near future' not in text:
        print(text)


def force_compact(tablet_id, local_table_id=1001):
    state = extract_force_compaction_state(tablet_internals(tablet_id))
    if state is None:
        start_force_compaction(tablet_id, local_table_id)
        time.sleep(0.1)
    while True:
        prev_state = state
        state = extract_force_compaction_state(tablet_internals(tablet_id))
        if state is None:
            break
        if state != 'Compacting' and state != prev_state:
            print(f'... {state}')
        time.sleep(1)


def setup_auth(auth_mode, viewer_url, auto_login):
    global VIEWER_HEADERS
    global TOKEN_AUTH

    if auth_mode == '' or auth_mode.lower() == 'disabled':
        if auto_login:
            print('--auto-login cannot be used with disabled auth', file=sys.stderr)
            sys.exit(1)
        VIEWER_HEADERS = {}
        TOKEN_AUTH = None
        return

    if auto_login:
        if not os.environ.get('YDB_USER'):
            print('YDB_USER is not set (required with --auto-login)', file=sys.stderr)
            sys.exit(1)
        if os.environ.get('YDB_PASSWORD') is None:
            print('YDB_PASSWORD is not set (required with --auto-login)', file=sys.stderr)
            sys.exit(1)
        if not viewer_url:
            print('--viewer-url is required with --auto-login', file=sys.stderr)
            sys.exit(1)

    token_path = DEFAULT_TOKEN_PATH
    try:
        if not os.path.isfile(token_path):
            if not auto_login:
                print(f'{token_path} does not exist')
                sys.exit(1)
            run_get_token(viewer_url, token_path)

        TOKEN_AUTH = TokenAuth(auth_mode, token_path, viewer_url, auto_login=auto_login)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)


def main():
    parser = ArgumentParser()
    parser.add_argument('--threads', type=int, default=10)
    parser.add_argument('--retries', type=int, default=10,
                        help='Number of retries for transient tablet/viewer errors (default: 10)')
    parser.add_argument('--viewer-url')
    parser.add_argument('--auth', dest="auth_mode", default='Login') # OAuth or Login
    parser.add_argument(
        '--auto-login',
        action='store_true',
        help=(
            'Periodically refresh ~/.ydb/token via get_token.py when the '
            'in-memory token is older than 5 minutes (requires YDB_USER/YDB_PASSWORD)'
        ),
    )
    parser.add_argument('--all', action='store_true')
    parser.add_argument('table')
    args = parser.parse_args()

    global MAX_RETRIES
    MAX_RETRIES = args.retries

    setup_auth(args.auth_mode, args.viewer_url, args.auto_login)

    # TODO: eliminate global variable
    global VIEWER_URL_BASE
    VIEWER_URL_BASE = args.viewer_url

    tablet_ids = []
    for p in describe_table(args.table)['PathDescription']['TablePartitions']:
        tablet_ids.append(int(p['DatashardId']))
    tablet_ids.sort()

    def generate_tasks():
        for i, tablet_id in enumerate(tablet_ids):
            yield i + 1, len(tablet_ids), tablet_id

    def process_task(task):
        index, count, tablet_id = task
        if not args.all and not extract_loaned_parts(tablet_internals(tablet_id)):
            print(f'[{time.ctime()}] [{index}/{count}] Skip {tablet_id}')
            return

        tablet_url = URL_EXECUTOR_INTERNALS.format(url_base=VIEWER_URL_BASE, tablet_id=tablet_id)
        print(f'[{time.ctime()}] [{index}/{count}] Compacting {tablet_id} url: {tablet_url}')
        force_compact(tablet_id)
        if extract_loaned_parts(tablet_internals(tablet_id)):
            print(f'[{time.ctime()}] [{index}/{count}] !!! WARNING !!! Tablet {tablet_id} has loaned parts after compaction')

    from multiprocessing.pool import ThreadPool

    with ThreadPool(args.threads) as pool:
        for _ in pool.imap_unordered(process_task, generate_tasks()):
            pass

if __name__ == '__main__':
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    main()
