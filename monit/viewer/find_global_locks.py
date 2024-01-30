#!/usr/bin/env python3

# sudo apt install python3-pip
# pip3 install lxml cssselect
# https://localhost:8766/viewer/json/whoami
# vi ~/.ydb/token

import re
import os
import sys
import requests
from argparse import ArgumentParser
from lxml import etree
from lxml.cssselect import CSSSelector
#from cStringIO import StringIO

VIEWER_URL_BASE = ''
VIEWER_HEADERS = {}

URL_NODE_TABLETS = '{url_base}/nodetabmon?action=browse_tablets'
URL_TABLET_COUNTERS = '{url_base}/tablets/counters?TabletID=%d'
URL_TABLET_INFO= '{url_base}/cms/api/datashard/json/getinfo?tabletid=%d'

SEL_THEAD = CSSSelector('table > thead > tr')
SEL_TBODY = CSSSelector('table > tbody')
RE_VALUE = re.compile('<pre>DataShard/LocksWholeShard: (\d+)</pre>', re.S)

def load_table(url, index=0):
    text = requests.get(url, headers=VIEWER_HEADERS, verify=False).text
    #tree = etree.parse(StringIO(text), etree.HTMLParser())
    tree = etree.ElementTree(etree.HTML(text))
    thead = SEL_THEAD(tree.getroot())[index]
    tbody = SEL_TBODY(tree.getroot())[index]
    headers = []
    for e in thead.iterchildren('th'):
        headers.append(''.join(e.itertext()))
    results = []
    for row in tbody.iterchildren('tr'):
        result = {}
        for i, col in enumerate(row.iterchildren('td')):
            result[headers[i]] = ''.join(col.itertext())
        results.append(result)
    return results

def get_value(tablet_id):
    url = URL_TABLET_COUNTERS.format(url_base=VIEWER_URL_BASE) % (tablet_id,)
    text = requests.get(url, headers=VIEWER_HEADERS, verify=False).text
    m = RE_VALUE.search(text)
    if m:
        return int(m.group(1))
    return None

def get_table_name(tablet_id:int):
    url = URL_TABLET_INFO.format(url_base=VIEWER_URL_BASE) % (tablet_id,)
    data = requests.get(url, headers=VIEWER_HEADERS, verify=False).json
    return data["UserTables"]["Path"]

def load_running_tablets():
    url = URL_NODE_TABLETS.format(url_base=VIEWER_URL_BASE)
    for result in load_table(url):
        if result['TabletType'] == 'DataShard':
            tablet_id = int(result['TabletID'])
            value = get_value(tablet_id)
            if value > 0:
                table_name = get_table_name(tablet_id)
                sys.stdout.write('%r %d %s\n' % (value, tablet_id, table_name))
                sys.stdout.flush()

def main():
    parser = ArgumentParser()
    parser.add_argument('--viewer-url')
    parser.add_argument('--auth', dest="auth_mode", default='Login') # OAuth or Login
    args = parser.parse_args()

    global VIEWER_HEADERS

    if args.auth_mode=='' or args.auth_mode.lower()=='disabled':
        VIEWER_HEADERS = {}
    else:
        token_path = os.path.expanduser("~/.ydb/token")
        if not os.path.isfile(token_path):
            print(f"{token_path} does not exist")
            sys.exit(1)

        token = open(token_path).read().strip()
        VIEWER_HEADERS = {
            'Authorization': str(args.auth_mode) + ' ' + token,
        }

    global VIEWER_URL_BASE
    VIEWER_URL_BASE = args.viewer_url

    load_running_tablets()

if __name__ == '__main__':
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    main()
