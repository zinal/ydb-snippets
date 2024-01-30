
#!/usr/bin/env python3
import re
import os
import sys
import requests
import time
from lxml import etree
from lxml.cssselect import CSSSelector
from cStringIO import StringIO

VIEWER_HEADERS = {}

URL_NODE_TABLETS = '{url_base}/nodetabmon?action=browse_tablets&node_id=2465'
URL_TABLET_COUNTERS = '{url_base}/tablets/counters?TabletID=%d'

SEL_THEAD = CSSSelector('table > thead > tr')
SEL_TBODY = CSSSelector('table > tbody')
RE_VALUE = re.compile('<pre>CachePinned: (\d+)</pre>', re.S)

def load_table(url, index=0):
    text = requests.get(url, headers=VIEWER_HEADERS, verify=False).text
    tree = etree.parse(StringIO(text), etree.HTMLParser())
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
    url = URL_TABLET_COUNTERS % (tablet_id,)
    text = requests.get(url, headers=VIEWER_HEADERS, verify=False).text
    m = RE_VALUE.search(text)
    if m:
        return int(m.group(1))
    return None

def load_running_tablets():
    for result in load_table(URL_NODE_TABLETS):
        if result['TabletType'] == 'DataShard':
            tablet_id = int(result['TabletID'])
            value = get_value(tablet_id)
            sys.stdout.write('%r %d\n' % (value, tablet_id))
            sys.stdout.flush()

def main():
    load_running_tablets()

if __name__ == '__main__':
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    main()
