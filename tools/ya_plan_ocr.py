# -*- coding: utf-8 -*-
"""청년안심주택 평면도 이미지(서울시 단지정보 상세 페이지)에서 전용면적을 글자 판독(Tesseract OCR)으로 읽어 data/ya_plans.json 에 저장.
사이트는 이 결과로 '기준 평수 이상 형'의 평면도만 사진 띠에 보여주고, 기준 미만·판독 실패는 접어 둔다.
판독 순서(앞의 것이 있으면 그것만 씀):
  1) 도면 제목의 'NN.NN A Type' / 'NN.NN형' (예: '단층형 17.84 A Type')
  2) '전용' 이 들어간 줄의 첫 소수(예: '주거전용면적 17.84㎡') — 실사용·공용·계약면적은 안 씀
  3) 그래도 없으면, 그 단지 입주현황 표의 형(17A → 17㎡대, A-15.33 → 15.33)과 정수부가 같은 소수 (약한 근거: how='known')
사용: python tools/ya_plan_ocr.py [--all]   (--all: 이미 읽은 이미지도 다시)"""
import os, re, sys, json, io, subprocess, tempfile, datetime, time
os.environ.setdefault('OMP_THREAD_LIMIT', '1')   # 여러 장을 동시에 읽을 때 tesseract 내부 스레드끼리 다투지 않게
from concurrent.futures import ThreadPoolExecutor
import requests
from PIL import Image, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
YA = os.path.join(ROOT, 'data', 'ya.json')
OUT = os.path.join(ROOT, 'data', 'ya_plans.json')
UA = {'User-Agent': 'Mozilla/5.0 (gonggo-map; +https://kimsangdeok.github.io/gonggo-map/)', 'Referer': 'https://soco.seoul.go.kr/youth/pgm/home/yohome/list.do?menuNo=400002'}

def langs():
    try:
        out = subprocess.run(['tesseract', '--list-langs'], capture_output=True, text=True, timeout=20).stdout
        return 'kor+eng' if 'kor' in out.split() else 'eng'
    except Exception:
        return 'eng'
LANG = langs()

NUM = r'(\d{2,3})\s?[.,·]\s?(\d{1,4})'   # 소수 넷째 자리까지(상봉동양엔파트 18.0282㎡·백악관타워 33.5879 같은 표 — 셋째 자리까지만 받던 때는 통째로 못 읽음)
def nums_in(t):
    return [float(a + '.' + b) for a, b in re.findall(r'(?<![\d.])' + NUM + r'(?![\d])', t)]

def known_types(c):
    ks = set()
    for g in ('special', 'general'):
        for r in (c.get('rows') or {}).get(g, []):
            ty = str(r.get('ty') or '')
            m = re.search(r'(\d{2,3}\.\d{1,3})', ty)
            if m: ks.add(('e', float(m.group(1))))
            else:
                m = re.search(r'(\d{2,3})', ty)
                if m: ks.add(('i', int(m.group(1))))
    return ks

def parse(text, ks):
    t = text.replace('㎡', ' ').replace('m²', ' ').replace('m2', ' ')
    # 1) 제목 'NN.NN A Type' / 'NN.NN형'
    hdr = [float(a + '.' + b) for a, b in re.findall(NUM + r'\s*[A-Za-z]{0,2}\s*[-]?\s*(?:T\s?y\s?p\s?e|TYPE|type|타입|형)', t)]
    hdr = [x for x in hdr if 10 <= x <= 120]
    if hdr: return sorted(set(hdr)), 'type'
    # 2) '전용' 줄
    lines = [l for l in t.splitlines() if l.strip()]
    jy = []
    for i, l in enumerate(lines):
        if '전용' in l and '공용' not in l:
            ns = [x for x in nums_in(l) if 10 <= x <= 120] or [x for x in nums_in(lines[i + 1] if i + 1 < len(lines) else '') if 10 <= x <= 120]
            if ns: jy.append(ns[0])
    if jy: return sorted(set(jy)), '전용'
    # 3) 단지 형과 정수부가 같은 소수
    out = []
    for x in nums_in(t):
        if not (10 <= x <= 120): continue
        for kind, v in ks:
            if (kind == 'e' and abs(x - v) <= 0.06) or (kind == 'i' and int(x) == v): out.append(x); break
    return (sorted(set(out)), 'known') if out else ([], '')

def ocr(path, psm):
    try:
        return subprocess.run(['tesseract', path, 'stdout', '-l', LANG, '--psm', str(psm)], capture_output=True, text=True, timeout=120).stdout
    except Exception as e:
        return ''

def read_one(url, ks):
    try:
        r = requests.get(url, headers=UA, timeout=60); r.raise_for_status()
        im = Image.open(io.BytesIO(r.content)).convert('L')
        f = 2 if im.width < 1000 else (1.5 if im.width < 1600 else 1)   # 작은 이미지만 키움(큰 걸 키우면 판독이 몇 배 느려짐)
        if f != 1: im = im.resize((int(im.width * f), int(im.height * f)), Image.LANCZOS)
        im = ImageOps.autocontrast(im)
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            im.save(f.name); p = f.name
        texts = [ocr(p, 6)]   # 블록 판독 한 번이면 도면 제목('17.84 A Type')이 대개 다 나옴
        if parse(texts[0], ks)[1] not in ('type', '전용'): texts.append(ocr(p, 11))   # 못 찾았을 때만 흩어진 글자 판독을 한 번 더
        os.unlink(p)
        m2, how = parse('\n'.join(texts), ks)
        return {'m2': m2, 'how': how, 'nums': [x for x in nums_in('\n'.join(texts)) if 10 <= x <= 200][:30], 'w': r.headers.get('content-length')}
    except Exception as e:
        return {'m2': [], 'how': '', 'err': repr(e)[:120]}

def main(redo=False):
    ya = json.load(open(YA, encoding='utf-8'))
    old = {}
    if os.path.exists(OUT):
        try: old = json.load(open(OUT, encoding='utf-8')).get('items', {})
        except Exception: old = {}
    jobs = []
    for c in ya.get('complexes', []):
        ks = known_types(c)
        for p in c.get('photos') or []:
            if p.get('k') != 'plan': continue
            if not redo and p['u'] in old and not old[p['u']].get('err'): continue
            jobs.append((p['u'], ks))
    print('lang', LANG, 'to read', len(jobs), 'cached', len(old))
    res = dict(old)
    keep = {p['u'] for c in ya.get('complexes', []) for p in (c.get('photos') or []) if p.get('k') == 'plan'}
    budget = float(os.environ.get('OCR_BUDGET_SEC', '2400')); t0 = time.time(); done = 0
    def save(final=False):
        r = {u: o for u, o in res.items() if u in keep}
        hows = {}
        for o in r.values(): hows[o.get('how') or 'none'] = hows.get(o.get('how') or 'none', 0) + 1
        json.dump({'updated': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y-%m-%d %H:%M KST'), 'lang': LANG,
                   'source': '서울시 청년안심주택 단지정보 상세 페이지 평면도 이미지 → Tesseract OCR(' + LANG + ')로 전용면적 판독. how: type=도면 제목(NN.NN Type), 전용=전용면적 줄, known=단지 형과 정수부 일치(약한 근거)',
                   'stats': hows, 'pending': max(0, len(jobs) - done), 'items': r}, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
        return hows
    # 시간 예산 안에서만 읽고(남은 건 다음 실행 때 이어서 — 이미 읽은 건 캐시), 25장마다 중간 저장
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = []
        for u, ks in jobs: futs.append((u, ex.submit(read_one, u, ks)))
        for u, f in futs:
            if time.time() - t0 > budget:
                for _, f2 in futs: f2.cancel()
                print('time budget reached; done', done, 'of', len(jobs)); break
            res[u] = f.result(); done += 1
            if done % 25 == 0: save(); print('progress', done, '/', len(jobs), round(time.time() - t0), 's', flush=True)
    res = {u: o for u, o in res.items() if u in keep}
    hows = save(True)
    print('wrote', OUT, len(res), hows)

if __name__ == '__main__':
    main(redo='--all' in sys.argv)
