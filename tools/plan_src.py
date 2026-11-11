# -*- coding: utf-8 -*-
"""평면도 원본 사본(data/plan_src) — GitHub Actions에서 실행. 개인정보 없음.
SH 주택정보·서울시 청년안심주택 평면도 원본은 그 사이트에만 있어, Claude가 평면도를 읽어 창·현관 표시(data/plan_marks.json)를
만들 때 볼 사본이 필요함(Claude 작업 공간은 그 사이트에 못 붙음). 화면은 계속 원본 주소를 씀 — 표시 자리는 그림 크기 비율(0~1)이라
사본을 줄여도 맞음.
입력: data/plan_src/list.json {"urls": [원본 URL, ...]}
결과: data/plan_src/<원본 URL 해시 16자>.jpg(긴 변 최대 2400px) + data/plan_src/index.json {updated, items: {URL: {f, w, h, sw, sh, at}}}
w·h = 원본 크기, sw·sh = 사본 크기. 이미 받은 것은 다시 안 받음(--force 면 다시)."""
import json, os, io, sys, hashlib, datetime
import requests
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = lambda *p: os.path.join(ROOT, 'data', 'plan_src', *p)
UA = 'Mozilla/5.0 (gonggo-map; +https://kimsangdeok.github.io/gonggo-map/)'
REF = {'i-sh.co.kr': 'https://www.i-sh.co.kr/houseinfo/main/mainPage.do',
       'soco.seoul.go.kr': 'https://soco.seoul.go.kr/youth/pgm/home/yohome/list.do?menuNo=400002'}
MAXS = 2400

def load(p, d):
    try: return json.load(open(p, encoding='utf-8'))
    except Exception: return d

def key(u): return hashlib.sha1(u.encode('utf-8')).hexdigest()[:16]

def main():
    force = '--force' in sys.argv
    urls = (load(D('list.json'), {}) or {}).get('urls') or []
    idx = load(D('index.json'), {}) or {}; items = idx.get('items') or {}
    now = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC'); ok = bad = 0
    for u in urls:
        if not force and u in items and os.path.exists(os.path.join(ROOT, items[u]['f'])): continue
        host = next((h for h in REF if h in u), None)
        try:
            r = requests.get(u, headers={'User-Agent': UA, **({'Referer': REF[host]} if host else {})}, timeout=60); r.raise_for_status()
            im = Image.open(io.BytesIO(r.content)); w, h = im.size; im = im.convert('RGB')
            s = min(1.0, MAXS / max(w, h))
            if s < 1: im = im.resize((round(w * s), round(h * s)), Image.LANCZOS)
            f = 'data/plan_src/%s.jpg' % key(u); im.save(os.path.join(ROOT, f), 'JPEG', quality=88, optimize=True)
            items[u] = {'f': f, 'w': w, 'h': h, 'sw': im.width, 'sh': im.height, 'at': now}; ok += 1
            print('ok', w, h, '->', im.size, u[-60:])
        except Exception as e:
            bad += 1; print('ERR', type(e).__name__, str(e)[:120], u[-60:])
    json.dump({'updated': now, 'about': '평면도 원본 사본 — Claude 평면도 읽기용(화면은 원본 주소)', 'items': items},
              open(D('index.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('done ok', ok, 'err', bad, 'total', len(items))

if __name__ == '__main__': main()
