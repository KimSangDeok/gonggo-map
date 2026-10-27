# -*- coding: utf-8 -*-
"""청년 매입임대 주택목록(호별 전용면적·임대조건) + 최종 경쟁률(주택군별 순위별 신청자) 결합 → data/mi_notice.json"""
import json, re, sys, os, importlib.util, collections
def load(name, path):
    sp = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m); return m
_d = os.path.dirname(os.path.abspath(__file__))
ml = load('ml', os.path.join(_d, 'mi_list.py')); mr = load('mr', os.path.join(_d, 'mi_rates.py')); mt = load('mt', os.path.join(_d, 'mi_types.py'))
LIST_PDF, RATES_PDF, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
NOTICE_PDF = sys.argv[4] if len(sys.argv) > 4 else os.path.join(os.path.dirname(_d), 'data', 'sh_files', '306214_5_notice.pdf')
rows, bad = ml.parse(LIST_PDF); rates = mr.parse(RATES_PDF)
# 공고문 '1. 공급주택' 표: 건물 유형(도시형생활주택/다세대/오피스텔…)·승강기·주차장·총세대수 (주택목록엔 없음) — 도로명 주소로 연결
H = {}
H2 = {}
for h in mt.parse(NOTICE_PDF): H.setdefault(mt.key(h['addr']), h); H2.setdefault(mt.lot_key(h['addr'], h['gu']), h)
no_type = 0
def norm(s): return re.sub(r'[\s\-_·,.\(\)\[\]]', '', s or '').lower()
# 경쟁률: 주택군 = (sec, gu, name, ty, sex)
def addrkey(a): return norm(re.sub(r'\(.*?\)', '', a or ''))
R = {}; RA = {}
for x in rates:
    k = (x['sec'], x['gu'], norm(x['name']), norm(x['ty']), x['sex']); R.setdefault(k, {})[x['rank']] = x
    ka = (x['sec'], x['gu'], addrkey(x['addr']), norm(x['ty']), x['sex']); RA.setdefault(ka, {})[x['rank']] = x
# 주택목록도 같은 키로 묶음(경쟁률 PDF 의 주택군 = 구분·구·주택명·주택형·성별)
G = collections.OrderedDict()
for r in rows:
    k = (r['sec'], r['gu'], norm(r['name']), norm(r['ty']), r['sex']); G.setdefault(k, {'sec': r['sec'], 'gu': r['gu'], 'name': r['name'], 'ty': r['ty'], 'sex': r['sex'], 'addr': r['addr'], 'struct': r['struct'], 'units': []})['units'].append(r)
groups = []; unmatched = 0
for k, g in G.items():
    rr = R.get(k) or RA.get((g['sec'], g['gu'], addrkey(g['addr']), norm(g['ty']), g['sex']))   # 이름이 '-'인 집은 주소로
    if rr is None:
        cands = [v for kk, v in R.items() if kk[:2] == k[:2] and kk[3] == k[3] and (kk[2].startswith(k[2]) or k[2].startswith(kk[2]))]   # 성별 표기·이름 꼬리 차이
        if not cands: cands = [v for kk, v in RA.items() if kk[:2] == k[:2] and kk[3] == k[3] and kk[2] == addrkey(g['addr'])]
        rr = cands[0] if len(cands) == 1 else None
    s = rr and rr.get('소계'); r1 = rr and rr.get('일반1순위'); r2 = rr and rr.get('일반2순위'); r3 = rr and rr.get('일반3순위')
    if not rr: unmatched += 1
    us = g['units']; m2s = [u['m2'] for u in us]
    h = H.get(mt.key(g['addr'])) or H2.get(mt.lot_key(g['addr'], g['gu']))   # 도로명 표기가 다르면(언남18길/언남로18길) 지번으로
    blds = sorted(set(t['bld'] for t in h['types'] if t['ty'] == g['ty'])) if h else []
    if not blds and h: blds = sorted(set(t['bld'] for t in h['types']))
    if not h: no_type += 1
    groups.append({'sec': g['sec'], 'gu': g['gu'], 'name': g['name'], 'ty': g['ty'], 'sex': g['sex'], 'addr': g['addr'], 'struct': g['struct'], 'n': len(us),
                   'bld': '·'.join(b.replace(' ', '·') for b in blds) if blds else None, 'lift': (h or {}).get('lift') or None, 'park': (h or {}).get('park') or None, 'tot': (h or {}).get('tot') or None, 'star': bool((h or {}).get('star')), 'm2_min': min(m2s), 'm2_max': max(m2s), 'm2s': sorted(m2s),
                   'p1': {'dep': min(u['p1']['dep'] or 0 for u in us) or None, 'rent': min(u['p1']['rent'] or 0 for u in us) or None, 'dep_hi': max(u['p1']['dep'] or 0 for u in us) or None, 'rent_hi': max(u['p1']['rent'] or 0 for u in us) or None},
                   'p23': {'dep': min(u['p23']['dep'] or 0 for u in us) or None, 'rent': min(u['p23']['rent'] or 0 for u in us) or None, 'dep_hi': max(u['p23']['dep'] or 0 for u in us) or None, 'rent_hi': max(u['p23']['rent'] or 0 for u in us) or None},
                   'rate': ({'n': s['n'], 'r1': r1['applicants'] if r1 else 0, 'r2': r2['applicants'] if r2 else 0, 'r3': r3['applicants'] if r3 else 0, 'sum': s['applicants'], 'rate': s['rate'], 'r1_fills': (r1['applicants'] if r1 else 0) >= s['n']} if s else None)})
json.dump({'updated': '2026-10-27', 'source': 'SH 2026년 1차 청년 매입임대주택 입주자 모집공고(306214) 첨부 주택목록(홈페이지 공개용) + 공고문 1. 공급주택 표(건물 유형·승강기·주차장) + 최종 청약 경쟁률(307073) PDF — pdfplumber 로 읽음', 'notice_url': 'https://www.i-sh.co.kr/app/lay2/program/S1T294C295/www/brd/m_241/view.do?multi_itm_seqs=1%2C2%2C4%2C8%2C16%2C32%2C64%2C128%2C256&seq=306214', 'rates_url': 'https://www.i-sh.co.kr/app/lay2/program/S1T294C295/www/brd/m_241/view.do?multi_itm_seqs=1%2C2%2C4%2C8%2C16%2C32%2C64%2C128%2C256&seq=307073', 'posted': '2026-06-26', 'apply': '2026-07-13~15', 'result': '2026-11-20 당첨자 발표 예정', 'total': len(rows), 'groups': groups, 'unmatched_groups': unmatched, 'no_type_groups': no_type, 'bad_lines': bad}, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False)
print('units', len(rows), 'groups', len(groups), 'unmatched', unmatched, 'no_type', no_type, 'bad', len(bad))
