#!/usr/bin/env python3
"""Obtain YDB Embedded UI session token and save it to ~/.ydb/token.

Authenticates via POST /login with credentials from YDB_USER / YDB_PASSWORD.
Writes the ydb_session_id cookie value into ~/.ydb/token.

Takes an exclusive file lock on the token file. If the file is newer than
5 minutes, skips the login and leaves the existing token unchanged.
"""

import fcntl
import os
import sys
import time
import requests
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from urllib.parse import urljoin


TOKEN_PATH = os.path.expanduser('~/.ydb/token')
TOKEN_MAX_AGE_SEC = 5 * 60


def fetch_session_token(viewer_url, user, password):
    base_url = viewer_url.rstrip('/') + '/'
    login_url = urljoin(base_url, 'login')

    response = requests.post(
        login_url,
        json={'user': user, 'password': password},
        headers={'Content-Type': 'application/json'},
        verify=False,
    )
    if not response.ok:
        raise RuntimeError(
            f'Login failed: HTTP {response.status_code}\n{response.text}'
        )

    token = response.cookies.get('ydb_session_id')
    if not token:
        # Some proxies/servers may expose Set-Cookie only in raw headers.
        for cookie in response.cookies:
            if cookie.name == 'ydb_session_id':
                token = cookie.value
                break
    if not token:
        raise RuntimeError('Login response did not contain Cookie ydb_session_id')
    return token


def token_is_fresh(path, max_age_sec=TOKEN_MAX_AGE_SEC):
    try:
        st = os.stat(path)
    except FileNotFoundError:
        return False
    if st.st_size == 0:
        return False
    return (time.time() - st.st_mtime) < max_age_sec


def update_token(token_path, viewer_url):
    """Lock token file, refresh it unless it is fresher than TOKEN_MAX_AGE_SEC."""
    os.makedirs(os.path.dirname(token_path) or '.', exist_ok=True)

    # Open (create if needed) for exclusive flock; do not truncate yet.
    fd = os.open(token_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            if token_is_fresh(token_path):
                print(
                    f'Token is fresh (< {TOKEN_MAX_AGE_SEC // 60} min), '
                    f'keeping {token_path}'
                )
                return False

            user = os.environ.get('YDB_USER')
            password = os.environ.get('YDB_PASSWORD')
            if not user:
                raise RuntimeError('YDB_USER is not set')
            if password is None:
                raise RuntimeError('YDB_PASSWORD is not set')

            token = fetch_session_token(viewer_url, user, password)

            os.lseek(fd, 0, os.SEEK_SET)
            os.ftruncate(fd, 0)
            data = (token + '\n').encode('utf-8')
            os.write(fd, data)
            os.fsync(fd)
            os.fchmod(fd, 0o600)
            print(f'Token saved to {token_path}')
            return True
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def main():
    parser = ArgumentParser(
        description='Fetch YDB UI session token and save it to ~/.ydb/token',
        formatter_class=RawDescriptionHelpFormatter,
        epilog='''\
Environment:
  YDB_USER       Login user name (required when token is missing/stale)
  YDB_PASSWORD   Login password (required when token is missing/stale)

The script takes an exclusive lock on the token file. If the file is newer
than 5 minutes, login is skipped and the existing token is kept.

Example:
  export YDB_USER=root
  export YDB_PASSWORD='...'
  ./get_token.py --viewer-url https://ycydb-s1:8765
''',
    )
    parser.add_argument(
        '--viewer-url',
        required=True,
        help='Base URL of YDB Embedded UI (e.g. https://host:8765)',
    )
    parser.add_argument(
        '--token-path',
        default=TOKEN_PATH,
        help=f'Path to write the token (default: {TOKEN_PATH})',
    )
    args = parser.parse_args()

    token_path = os.path.expanduser(args.token_path)
    try:
        update_token(token_path, args.viewer_url)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    main()
