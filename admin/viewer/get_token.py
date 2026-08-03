#!/usr/bin/env python3
"""Obtain YDB Embedded UI session token and save it to ~/.ydb/token.

Authenticates via POST /login with credentials from YDB_USER / YDB_PASSWORD.
Writes the ydb_session_id cookie value into ~/.ydb/token.
"""

import os
import sys
import requests
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from urllib.parse import urljoin


TOKEN_PATH = os.path.expanduser('~/.ydb/token')


def main():
    parser = ArgumentParser(
        description='Fetch YDB UI session token and save it to ~/.ydb/token',
        formatter_class=RawDescriptionHelpFormatter,
        epilog='''\
Environment:
  YDB_USER       Login user name (required)
  YDB_PASSWORD   Login password (required)

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

    user = os.environ.get('YDB_USER')
    password = os.environ.get('YDB_PASSWORD')
    if not user:
        print('YDB_USER is not set', file=sys.stderr)
        sys.exit(1)
    if password is None:
        print('YDB_PASSWORD is not set', file=sys.stderr)
        sys.exit(1)

    base_url = args.viewer_url.rstrip('/') + '/'
    login_url = urljoin(base_url, 'login')

    response = requests.post(
        login_url,
        json={'user': user, 'password': password},
        headers={'Content-Type': 'application/json'},
        verify=False,
    )
    if not response.ok:
        print(
            f'Login failed: HTTP {response.status_code}\n{response.text}',
            file=sys.stderr,
        )
        sys.exit(1)

    token = response.cookies.get('ydb_session_id')
    if not token:
        # Some proxies/servers may expose Set-Cookie only in raw headers.
        for cookie in response.cookies:
            if cookie.name == 'ydb_session_id':
                token = cookie.value
                break
    if not token:
        print(
            'Login response did not contain Cookie ydb_session_id',
            file=sys.stderr,
        )
        sys.exit(1)

    token_path = os.path.expanduser(args.token_path)
    os.makedirs(os.path.dirname(token_path) or '.', exist_ok=True)
    with open(token_path, 'w') as f:
        f.write(token)
        f.write('\n')
    os.chmod(token_path, 0o600)

    print(f'Token saved to {token_path}')


if __name__ == '__main__':
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    main()
