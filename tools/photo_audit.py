# -*- coding: utf-8 -*-
"""점검용: 사이트에 뜨는 SH 주택정보 사진(SH 평면도·전경·실내)을 받아 단지별 모아보기 그림으로 만든다.
사진이 그 단지·그 형 것인지 눈으로 대조하는 용도 — 결과는 Actions 아티팩트(photo-audit)로만 남기고 저장소에는 커밋하지 않음.
사용: python tools/photo_audit.py  → audit_out/NN_<단지>.jpg, audit_out/index.json"""
import json, os, io, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sources import S
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'audit_out'); os.makedirs(OUT, exist_ok=True)
FONT = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
def font(sz):
    try: return ImageFont.truetype(FONT, sz)
    except Exception: return ImageFont.load_default()
F_CAP, F_HEAD = font(22), font(30)
TW, TH, CAP, COLS, PER = 480, 360, 44, 3, 12          # 칸 크기·글자띠·열 수·한 장 최대 칸

fact = json.load(open(os.path.join(ROOT, 'data', 'fact.json'), encoding='utf-8'))['fact']
raw = json.load(open(os.path.join(ROOT, 'data', 'raw.json'), encoding='utf-8'))
cache = {}
def get(u):
    if u in cache: return cache[u]
    im = None
    try:
        r = S.get(u, timeout=40, headers={'Referer': 'https://www.i-sh.co.kr/houseinfo/main/mainPage.do'})
        if r.ok and r.content[:2] in (b'\xff\xd8', b'\x89P', b'GI', b'BM', b'RI'):
            im = Image.open(io.BytesIO(r.content)).convert('RGB')
    except Exception as e:
        print('fail', u, repr(e))
    cache[u] = im
    return im

index, sheet_no = [], 0
for key in sorted(fact):
    v = fact[key]
    tiles = []
    if v.get('plan'): tiles.append(('SH 평면도' + (' ' + v['type']['sp'] + '형' if v.get('type') else ''), v['plan']))
    for u in v.get('photos') or []: tiles.append(('전경', u))
    for r in v.get('rooms') or []: tiles.append(('실내 · ' + r['t'], r['u']))
    if not tiles: continue
    name, m2 = key.split('|')
    ty = v.get('type') or {}
    head = f"{name}  (사이트 형 {m2 or '-'}㎡ · SH {ty.get('sp', '-')}형 {ty.get('ar', '')}㎡ {ty.get('cls', '')})"
    for part in range(0, len(tiles), PER):
        chunk = tiles[part:part + PER]
        rows = (len(chunk) + COLS - 1) // COLS
        W, H = COLS * TW, 60 + rows * (TH + CAP)
        sh = Image.new('RGB', (W, H), 'white'); d = ImageDraw.Draw(sh)
        d.text((12, 12), head + (f'  [{part // PER + 1}]' if len(tiles) > PER else ''), font=F_HEAD, fill='black')
        for i, (lab, u) in enumerate(chunk):
            x, y = (i % COLS) * TW, 60 + (i // COLS) * (TH + CAP)
            im = get(u)
            if im:
                t = im.copy(); t.thumbnail((TW - 8, TH - 8))
                sh.paste(t, (x + (TW - t.width) // 2, y + (TH - t.height) // 2))
            else:
                d.rectangle([x + 4, y + 4, x + TW - 4, y + TH - 4], outline='red', width=3); d.text((x + 20, y + 20), '받기 실패', font=F_CAP, fill='red')
            fn = u.rsplit('/', 1)[-1]
            d.rectangle([x, y + TH, x + TW, y + TH + CAP], fill='#eeeeee')
            d.text((x + 6, y + TH + 4), (lab + ' · ' + fn)[:46], font=F_CAP, fill='black')
            index.append({'sheet': sheet_no, 'key': key, 'label': lab, 'url': u, 'ok': bool(im)})
        safe = re.sub(r'[^0-9A-Za-z가-힣]+', '_', name)[:30]
        sh.save(os.path.join(OUT, f'{sheet_no:02d}_{safe}.jpg'), 'JPEG', quality=82)
        sheet_no += 1
# ---------- 청년안심주택(서울시 단지정보 사진): 내 조건에 드는 단지(청년 형 8평 이상)만 — 화면과 같은 규칙 ----------
# 대표 사진(main)은 늘 보이고, 평면도(plan)는 도면 글자 판독(ya_plans.json) 전용면적이 8평(26.45㎡) 이상이면 띠에, 아니면 접힘
import importlib.util
_spec = importlib.util.spec_from_file_location('nn', os.path.join(ROOT, 'tools', 'notify_new.py'))
nn = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(nn)
ya = nn.apply_ya_fix(json.load(open(os.path.join(ROOT, 'data', 'ya.json'), encoding='utf-8')))   # 형 이름 ≠ 전용면적 고침 반영
ocr = json.load(open(os.path.join(ROOT, 'data', 'ya_plans.json'), encoding='utf-8')).get('items', {})
FLOOR = 26.45
for c in sorted(ya.get('complexes', []), key=lambda c: c.get('name', '')):
    ok, _ = nn.ya_split(c)
    if not ok: continue
    ph = c.get('photos') or []
    tiles = [('대표 · ' + (x.get('t') or '')[:12], x['u']) for x in ph if x.get('k') == 'main'] or ([('대표', c['img'])] if c.get('img') else [])
    for x in ph:
        if x.get('k') != 'plan': continue
        o = ocr.get(x['u']) or {}
        ms = [m for m in (o.get('m2') or []) if 10 <= m <= 120]
        where = '띠' if any(m >= FLOOR for m in ms) else ('접힘<8평' if ms else '접힘?')
        tiles.append((f"평면 {'·'.join(str(m) for m in ms) or '?'}㎡ [{o.get('how', '')}] {where}", x['u']))
    if not tiles: continue
    rows = '·'.join(sorted({str(r.get('ty')) for r, _ in ok}))[:60]
    head = f"[청년안심] {c.get('name')}  (청년 8평↑ 형: {rows})"
    for part in range(0, len(tiles), PER):
        chunk = tiles[part:part + PER]
        nrows = (len(chunk) + COLS - 1) // COLS
        sh = Image.new('RGB', (COLS * TW, 60 + nrows * (TH + CAP)), 'white'); d = ImageDraw.Draw(sh)
        d.text((12, 12), head + (f'  [{part // PER + 1}]' if len(tiles) > PER else ''), font=F_HEAD, fill='black')
        for i, (lab, u) in enumerate(chunk):
            x0, y0 = (i % COLS) * TW, 60 + (i // COLS) * (TH + CAP)
            im = get(u)
            if im:
                t = im.copy(); t.thumbnail((TW - 8, TH - 8)); sh.paste(t, (x0 + (TW - t.width) // 2, y0 + (TH - t.height) // 2))
            else:
                d.rectangle([x0 + 4, y0 + 4, x0 + TW - 4, y0 + TH - 4], outline='red', width=3); d.text((x0 + 20, y0 + 20), '받기 실패', font=F_CAP, fill='red')
            d.rectangle([x0, y0 + TH, x0 + TW, y0 + TH + CAP], fill='#eeeeee')
            d.text((x0 + 6, y0 + TH + 4), lab[:46], font=F_CAP, fill='black')
            index.append({'sheet': sheet_no, 'key': 'ya:' + str(c.get('code') or c.get('name')), 'label': lab, 'url': u, 'ok': bool(im)})
        safe = re.sub(r'[^0-9A-Za-z가-힣]+', '_', c.get('name', ''))[:30]
        sh.save(os.path.join(OUT, f'{sheet_no:03d}_ya_{safe}.jpg'), 'JPEG', quality=82)
        sheet_no += 1
# ---------- 원본 크기로 볼 이미지(FULL_URLS): 긴 소개 그림·여러 형 한 장은 글자를 읽을 수 있게 원본 해상도로 잘라 저장 ----------
for n, u in enumerate((os.environ.get('FULL_URLS') or '').split()):
    im = get(u)
    if not im: print('full fail', u); continue
    W = min(im.width, 1400)
    if im.width > W: im = im.resize((W, int(im.height * W / im.width)))
    step = int(W * 1.1)
    for k, y in enumerate(range(0, im.height, step)):
        im.crop((0, y, im.width, min(im.height, y + step))).save(os.path.join(OUT, f'full_{n:02d}_{k:02d}.jpg'), 'JPEG', quality=88)
    index.append({'full': n, 'url': u, 'w': im.width, 'h': im.height, 'parts': (im.height + step - 1) // step})
json.dump(index, open(os.path.join(OUT, 'index.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('sheets', sheet_no, 'images', len(index), 'failed', sum(1 for x in index if not x.get('ok', True)))
