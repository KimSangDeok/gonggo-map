# -*- coding: utf-8 -*-
"""SH 청년안심주택(공공임대) 입주자모집공고문 PDF → 단지·형별 행 (word 좌표 기반)
출력 행: {sec(신규/재공급), danji, addr, ty(공급유형), m2(평면 전용), who, n, A:{dep,rent}, B:{dep,rent}}"""
import pdfplumber, re, sys, json

def num(s):
    s = (s or '').replace(',', '').strip()
    try: return float(s) if '.' in s else int(s)
    except: return None

def parse(path):
    pdf = pdfplumber.open(path); out = []; sec = ''
    for pi, pg in enumerate(pdf.pages):
        txt = pg.extract_text() or ''
        m = re.search(r'[■○]\s*(신규공급|재공급|셰어형 예비입주자)', txt)
        if m: sec = m.group(1)
        for tb in pg.find_tables():
            cells = tb.cells
            allc = [(c, ' '.join((pg.crop(c).extract_text() or '').split())) for c in cells if c[1] < tb.bbox[1] + 90]
            dj = [c for c, t in allc if t.startswith('단지명')]
            if not dj: continue
            hb0 = dj[0][3]
            heads = [(c, t) for c, t in allc if c[3] <= hb0 + 1]
            ht = ' '.join(t for _, t in heads)
            if '평면' not in ht: continue
            # 열 경계: 머리글 셀 x 범위
            col = {}
            for c, t in heads:
                if t.startswith('단지명'): col['danji'] = (c[0], c[2])
                elif t.startswith('공급 유형') or t.startswith('공급유형'): col['ty'] = (c[0], c[2])
                elif t.startswith('평면'): col['m2'] = (c[0], c[2])
                elif t.startswith('신청'): col['who'] = (c[0], c[2])
                elif t.startswith('공급 호수') or t.startswith('공급호수'):
                    if 'n' not in col: col['n'] = (c[0], c[2])
                    else: col['grade'] = (c[0], c[2])
                elif t == '계': col['dep'] = (c[0], c[2])
                elif re.match(r'월\s*임\s*대\s*료', t): col['rent'] = (c[0], c[2])
                elif t.startswith('임대료') and '구분' in t: col['grade'] = (c[0], c[2])
            if 'n' not in col:
                for c, t in heads:
                    if '호수' in t or '세대' in t: col['n'] = (c[0], c[2]); break
            if 'ty' not in col or 'm2' not in col or 'n' not in col:
                print('SKIP table page', pi + 1, [t for _, t in heads], file=sys.stderr); continue
            hb = max(c[3] for c, _ in heads)   # header bottom
            words = [w for w in pg.extract_words(x_tolerance=1.5, keep_blank_chars=True) if w['top'] >= hb - 1 and w['bottom'] <= tb.bbox[3] + 1]
            def inx(w, k): x = (w['x0'] + w['x1']) / 2; return col[k][0] - 1 <= x <= col[k][1] + 1
            # 형 행 밴드: 공급유형 열의 셀
            bands = sorted([c for c in cells if abs(c[0] - col['ty'][0]) < 2 and c[1] >= hb - 1], key=lambda c: c[1])
            # 단지 경계: 단지명 열 왼쪽에서 시작하는 가로선
            tops = sorted({round(e['top']) for e in pg.edges if e['orientation'] == 'h' and e['x0'] <= tb.bbox[0] + 3 and e['x1'] >= col['danji'][1] - 3 and e['top'] >= hb - 1})
            def danji_for(y):
                lo = max([t for t in tops if t <= y + 1], default=hb); hi = min([t for t in tops if t > y + 1], default=tb.bbox[3])
                ws = [w for w in words if inx(w, 'danji') and lo - 1 <= w['top'] and w['bottom'] <= hi + 1]
                ws.sort(key=lambda w: (round(w['top']), w['x0']))
                lines = {}
                for w in ws: lines.setdefault(round(w['top'] / 4), []).append(w['text'])
                ls = [' '.join(v) for _, v in sorted(lines.items())]
                return ls
            for b in bands:
                y0, y1 = b[1], b[3]
                def cell(k): return ' '.join(w['text'] for w in sorted([w for w in words if inx(w, k) and w['top'] >= y0 - 1 and w['bottom'] <= y1 + 1], key=lambda w: (round(w['top']), w['x0'])))
                ty, m2, who, n = cell('ty'), cell('m2'), cell('who'), cell('n')
                if not m2 or not re.search(r'\d', m2): continue
                row = {'sec': sec, 'page': pi + 1, 'ty': ty, 'm2': num(re.search(r'[\d.]+', m2).group(0)), 'who': who, 'n': num(re.search(r'\d+', n).group(0)) if re.search(r'\d+', n) else None}
                ls = danji_for((y0 + y1) / 2); row['danji'] = ls[0] if ls else ''; row['addr'] = ' '.join(ls[1:]) if len(ls) > 1 else ''
                # A/B/C/D 소행
                gws = [w for w in words if 'grade' in col and inx(w, 'grade') and w['top'] >= y0 - 1 and w['bottom'] <= y1 + 1 and re.fullmatch(r'[A-D]', w['text'])]
                for g in gws:
                    gy0, gy1 = g['top'] - 8, g['bottom'] + 8
                    dep = ' '.join(w['text'] for w in words if 'dep' in col and inx(w, 'dep') and abs(((w['top'] + w['bottom']) / 2) - ((g['top'] + g['bottom']) / 2)) < 7)
                    rent = ' '.join(w['text'] for w in words if 'rent' in col and inx(w, 'rent') and abs(((w['top'] + w['bottom']) / 2) - ((g['top'] + g['bottom']) / 2)) < 7)
                    row[g['text']] = {'dep': num(dep), 'rent': num(rent)}
                out.append(row)
    return out

if __name__ == '__main__':
    rows = parse(sys.argv[1])
    print(json.dumps(rows, ensure_ascii=False, indent=0)[:6000])
    print('rows', len(rows), 'sum n', sum(r['n'] or 0 for r in rows))
