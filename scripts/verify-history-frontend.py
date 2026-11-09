#!/usr/bin/env python3
"""Verify that the HTTP entrypoint serves both the new card JS and card CSS."""
from html.parser import HTMLParser
import json
import urllib.request
from urllib.parse import urlsplit


class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        for key in ('src', 'href'):
            value = attrs.get(key, '')
            if value.startswith('/_next/static/') and urlsplit(value).path.endswith(('.js', '.css')):
                self.urls.add(value)


def check_frontend(base='http://127.0.0.1:3000'):
    with urllib.request.urlopen(base + '/?activation-check=history-three-columns', timeout=15) as response:
        parser = Assets()
        parser.feed(response.read().decode())
    matched = {'js': [], 'css': []}
    for path in sorted(parser.urls):
        with urllib.request.urlopen(base + path, timeout=15) as response:
            body = response.read().decode()
        kind = urlsplit(path).path.rsplit('.', 1)[-1]
        if 'jobCardPreview' in body and (kind != 'css' or 'historyCardSweep' in body):
            matched[kind].append(path)
    if not matched['js'] or not matched['css']:
        raise RuntimeError('Port frontend masih menyajikan aset lama atau campuran. Build kontainer saja belum membuktikan aktivasi; periksa direktori runtime dan pemetaan port.')
    return matched


if __name__ == '__main__':
    import sys
    try:
        print(json.dumps(check_frontend(sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:3000')))
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
