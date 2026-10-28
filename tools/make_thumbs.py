# -*- coding: utf-8 -*-
"""사진 띠용 작은 그림(썸네일) — GitHub Actions에서 실행. 개인정보 없음.
SH 주택정보·서울시 청년안심주택 사진은 원본이 수 MB(수천 px)라, 폰에서 사진 띠(한 칸 128×96)를 넘길 때
원본을 통째로 풀어(디코딩) 시간·메모리를 크게 씀 → 스크롤이 끊김. 띠에는 칸에 보이는 부분만 384×288(3배 화소) JPEG로
잘라 쓰고, 누르면(크게 보기) 원본을 연다. 자르는 자리는 화면과 같게: 평면도는 위쪽, 나머지는 가운데(object-fit: cover).
이미 만든 것은 다시 받지 않음(원본 URL 기준). 지금 화면에 안 쓰는 썸네일은 지움.
결과: data/thumbs/<원본 URL 해시 16자>.jpg, data/thumbs.json {updated, count, items: {원본 URL: {t, w, h, kb}}}
한 장에 여러 형이 든 청년안심 평면도(data/ya_fix.json plans[URL].crops — 사람이 형마다 영역을 적어 둠)는 형별로 잘라
data/thumbs/<해시>_c<i>.jpg(크게 보기용, 가로 최대 1600px) + _c<i>_t.jpg(띠용)도 만듦 → items[URL].crops = [{f, t, w, h}], cs = 영역 서명"""
import json, os, io, hashlib, time, datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = lambda *p: os.path.join(ROOT, 'data', *p)
OUTD, IDX = D('thumbs'), D('thumbs.json')
TW, TH, Q = 384, 288, 70
BUDGET = int(os.environ.get('THUMB_BUDGET_SEC', '1500'))
UA = 'Mozilla/5.0 (gonggo-map; +https://kimsangdeok.github.io/gonggo-map/)'
REF = {'i-sh.co.kr': 'https://www.i-sh.co.kr/houseinfo/main/mainPage.do',
       'soco.seoul.go.kr': 'https://soco.seoul.go.kr/youth/pgm/home/yohome/list.do?menuNo=400002'}

def load(p, d):
    try: return json.load(open(p, encoding='utf-8'))
    except Exception: return d

def wanted():
    """화면 사진 띠에 들어가는 원본 URL → 자르는 자리('top' 평면도 / 'center' 나머지). 순서 유지"""
    out = {}
    for v in (load(D('fact.json'), {}).get('fact') or {}).values():
        for r in v.get('rooms') or []: out.setdefault(r['u'], 'center')
        for u in v.get('photos') or []: out.setdefault(u, 'center')
        if v.get('plan'): out.setdefault(v['plan'], 'top')
    for c in load(D('ya.json'), {}).get('complexes') or []:
        if c.get('img'): out.setdefault(c['img'], 'center')
        for x in c.get('photos') or []: out.setdefault(x['u'], 'top' if x.get('k') == 'plan' else 'center')
    return out

def key(u): return hashlib.sha1(u.encode('utf-8')).hexdigest()[:16]

def crops_wanted():
    """여러 형 한 장 평면도 → 형별 영역 [{box: [x0, y0, x1, y1](0~1 비율), label, m2, k}] (data/ya_fix.json)"""
    return {u: v['crops'] for u, v in ((load(D('ya_fix.json'), {}) or {}).get('plans') or {}).items() if v.get('crops')}

def crop_sig(cr): return hashlib.sha1(json.dumps([c['box'] for c in cr]).encode()).hexdigest()[:8]

def crop_files(u, n):
    return [('data/thumbs/%s_c%d.jpg' % (key(u), i), 'data/thumbs/%s_c%d_t.jpg' % (key(u), i)) for i in range(n)]

def make_crops(u, content, cr):
    """원본 해상도에서 형별로 잘라 크게 보기용(가로 ≤1600)·띠용(384×288) 저장. 띠용은 가로로 넓으면 위아래 흰 여백, 세로로 길면 위쪽"""
    full = Image.open(io.BytesIO(content)).convert('RGB'); W, H = full.size; out = []
    for (rf, rt), c in zip(crop_files(u, len(cr)), cr):
        x0, y0, x1, y1 = c['box']
        im = full.crop((round(x0 * W), round(y0 * H), round(x1 * W), round(y1 * H)))
        if im.width > 1600: im = im.resize((1600, round(im.height * 1600 / im.width)), Image.LANCZOS)
        im.save(os.path.join(ROOT, rf), 'JPEG', quality=85, optimize=True, progressive=True)
        cw, ch = im.size
        if cw * TH > ch * TW:   # 가로로 넓음 → 4:3 흰 바탕 가운데
            bg = Image.new('RGB', (cw, cw * TH // TW), 'white'); bg.paste(im, (0, (bg.height - ch) // 2)); t = bg
        else:
            t = im.crop((0, 0, cw, cw * TH // TW))
        t.resize((TW, TH), Image.LANCZOS).save(os.path.join(ROOT, rt), 'JPEG', quality=Q, optimize=True, progressive=True)
        out.append({'f': rf, 't': rt, 'w': cw, 'h': ch})
    return out

def make(u, pos, cr=None):
    host = next((h for h in REF if h in u), None)
    r = requests.get(u, headers={'User-Agent': UA, **({'Referer': REF[host]} if host else {})}, timeout=60)
    r.raise_for_status()
    extra = {'crops': make_crops(u, r.content, cr), 'cs': crop_sig(cr)} if cr else {}
    im = Image.open(io.BytesIO(r.content)); w, h = im.size
    if im.format == 'JPEG': im.draft('RGB', (TW * 2, TH * 2))   # 큰 JPEG는 줄여 풀기(빠름)
    im = im.convert('RGB'); sw, sh = im.size
    # 칸(4:3)에 보이는 영역만: 가로가 넓으면 좌우 가운데, 세로가 길면 평면도는 위·나머지는 가운데
    if sw * TH > sh * TW:
        cw = sh * TW // TH; x0 = (sw - cw) // 2; box = (x0, 0, x0 + cw, sh)
    else:
        ch = sw * TH // TW; y0 = 0 if pos == 'top' else (sh - ch) // 2; box = (0, y0, sw, y0 + ch)
    im = im.crop(box).resize((TW, TH), Image.LANCZOS)
    rel = 'data/thumbs/' + key(u) + '.jpg'
    im.save(os.path.join(ROOT, rel), 'JPEG', quality=Q, optimize=True, progressive=True)
    return {'t': rel, 'w': w, 'h': h, 'kb': round(len(r.content) / 1024), **extra}

def main():
    os.makedirs(OUTD, exist_ok=True)
    want = wanted(); old = (load(IDX, {}) or {}).get('items') or {}; CR = crops_wanted()
    items, todo = {}, []
    for u, pos in want.items():
        o, cr = old.get(u), CR.get(u)
        ok = o and os.path.exists(os.path.join(ROOT, o['t']))
        if ok and cr: ok = o.get('cs') == crop_sig(cr) and all(os.path.exists(os.path.join(ROOT, f)) for p in crop_files(u, len(cr)) for f in p)
        if ok and not cr and o.get('crops'): ok = False   # 자르기를 없앴으면 다시 만들어 crops 정보를 지움
        if ok: items[u] = o
        else: todo.append((u, pos, cr))
    print('wanted', len(want), 'cached', len(items), 'todo', len(todo), 'crops', sum(1 for t in todo if t[2]), flush=True)
    t0, fail = time.time(), []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(make, u, pos, cr): u for u, pos, cr in todo}
        for f in as_completed(futs):
            u = futs[f]
            try: items[u] = f.result()
            except Exception as e: fail.append(u); print('fail', u, repr(e)[:120], flush=True)
            if time.time() - t0 > BUDGET:
                print('budget reached — rest next run', flush=True)
                for g in futs: g.cancel()
                break
    # 화면에 안 쓰는 썸네일 파일 지움
    keep = {os.path.basename(v['t']) for u, v in items.items() if u in want} | {os.path.basename(c[k]) for u, v in items.items() if u in want for c in v.get('crops') or [] for k in ('f', 't')}
    gone = [f for f in os.listdir(OUTD) if f.endswith('.jpg') and f not in keep]
    for f in gone: os.remove(os.path.join(OUTD, f))
    items = {u: items[u] for u in want if u in items}
    kb = [v['kb'] for v in items.values()]
    big = sorted(items.values(), key=lambda v: -v['kb'])[:5]
    stat = {'orig_mb': round(sum(kb) / 1024, 1), 'orig_kb_avg': round(sum(kb) / max(1, len(kb))), 'orig_kb_max': max(kb or [0]),
            'orig_px_max': max((v['w'] * v['h'] for v in items.values()), default=0),
            'thumb_mb': round(sum(os.path.getsize(os.path.join(ROOT, v['t'])) for v in items.values()) / 1048576, 1)}
    json.dump({'updated': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y-%m-%d %H:%M KST'),
               'note': '사진 띠용 384×288 썸네일(칸에 보이는 부분만). 크게 보기는 원본 URL', 'count': len(items), 'stat': stat,
               'items': items}, open(IDX, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print('done', len(items), 'new', len(todo) - len(fail), 'fail', len(fail), 'removed', len(gone), stat, 'biggest', big, flush=True)

if __name__ == '__main__':
    main()
