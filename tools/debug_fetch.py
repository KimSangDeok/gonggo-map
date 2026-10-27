# -*- coding: utf-8 -*-
"""개발용: 컨테이너에서 못 여는 사이트(soco.seoul.go.kr 등)의 HTML/JS/JSON을 Actions 러너가 받아 data/debug/ 에 저장. 개인정보 없음.
사용: URLS='url1 url2' python tools/debug_fetch.py  (POST는 'url|a=1&b=2' 형식)"""
import os, sys, re, json, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sources import S
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'debug')
os.makedirs(OUT, exist_ok=True)
for f in os.listdir(OUT): os.remove(os.path.join(OUT, f))
index = []
for spec in os.environ.get('URLS', '').split():
    url, _, post = spec.partition('|')
    try:
        if post:
            r = S.post(url, data=dict(p.split('=', 1) for p in post.split('&') if '=' in p), timeout=60, headers={'X-Requested-With': 'XMLHttpRequest', 'Referer': url})
        else:
            hdr = {}
            m = re.search(r'innoFD\.do.*[?&]seq=(\d+)', url)   # SH 첨부 다운로드는 게시물 Referer 가 있어야 500 이 안 남
            if m: hdr['Referer'] = 'https://www.i-sh.co.kr/app/lay2/program/S1T294C295/www/brd/m_241/view.do?multi_itm_seqs=1%2C2%2C4%2C8%2C16%2C32%2C64%2C128%2C256&seq=' + m.group(1)
            r = S.get(url, timeout=90, headers=hdr)
        name = re.sub(r'[^A-Za-z0-9]+', '_', url.split('//', 1)[-1])[:80] + '_' + hashlib.md5(spec.encode()).hexdigest()[:6]
        ct = (r.headers.get('content-type') or '').lower()
        ext = '.json' if 'json' in ct else ('.pdf' if ('pdf' in ct or r.content[:5] == b'%PDF-') else ('.js' if url.endswith('.js') else '.html'))
        open(os.path.join(OUT, name + ext), 'wb').write(r.content[:12_000_000])   # 공고문 PDF 도 받을 수 있게 12MB
        index.append({'url': url, 'post': post, 'status': r.status_code, 'type': r.headers.get('content-type'), 'bytes': len(r.content), 'file': name + ext})
    except Exception as e:
        index.append({'url': url, 'post': post, 'error': repr(e)})
json.dump(index, open(os.path.join(OUT, 'index.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps(index, ensure_ascii=False, indent=1))
