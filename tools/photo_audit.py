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
json.dump(index, open(os.path.join(OUT, 'index.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('sheets', sheet_no, 'images', len(index), 'failed', sum(1 for x in index if not x['ok']))
