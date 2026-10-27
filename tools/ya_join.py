# -*- coding: utf-8 -*-
"""청년안심 공공임대 공고문 행(8평 이상 청년형) + 경쟁률 PDF 행 결합 → data/ya_notice.json"""
import json, re, sys, importlib.util
def load(name, path):
    sp = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m); return m
import os; _d = os.path.dirname(os.path.abspath(__file__)); yn = load('yn', os.path.join(_d, 'ya_notice.py')); yr = load('yr', os.path.join(_d, 'ya_rates.py'))
MIN = 26.45
def norm(s): return re.sub(r'\(.*?\)', '', s or '').replace(' ', '').lower()
def tynum(t): m = re.search(r'\d{2}(?:\.\d+)?', t or ''); return m.group(0) if m else ''
rounds = [
  {'id': 'YA26-1', 'label': '2026 1차', 'seq': '302646', 'posted': '2026-03-31', 'apply': '2026-04-10~14', 'pdf': 'data/sh_files/302646_1_notice.pdf', 'rates': None, 'rates_seq': None, 'total_txt': '573세대(신규 466 · 재공급 107)'},
  {'id': 'YA26-2', 'label': '2026 2차', 'seq': '309925', 'posted': '2026-07-31', 'apply': '2026-08-11~13', 'pdf': 'data/sh_files/309925_1_notice.pdf', 'rates': 'data/sh_files/308650_1_notice.pdf', 'rates_seq': '308650', 'total_txt': '공고 본문 595세대(신규 363 · 재공급 232) · 정정 후 단지표 합계 577세대(349 · 228)'},
]
VIEW = 'https://www.i-sh.co.kr/app/lay2/program/S1T294C295/www/brd/m_241/view.do?multi_itm_seqs=1%2C2%2C4%2C8%2C16%2C32%2C64%2C128%2C256&seq='
out = []
for rd in rounds:
    rows = yn.parse(rd['pdf'])
    rates = yr.parse(rd['rates']) if rd['rates'] else []
    youth = [r for r in rows if '청년' in r['who'] and not re.search(r'셰어|팀', (r['ty'] or '') + r['sec'])]
    ok = [r for r in youth if r['m2'] and r['m2'] >= MIN and (r['n'] or 0) > 0]
    small_n = sum((r['n'] or 0) for r in youth if r['m2'] and r['m2'] < MIN)
    # 경쟁률 결합: 단지명(괄호 제거) 포함관계 + 형 숫자. 같은 단지·같은 숫자가 여럿(홍대크리원 30A/30B)이면 전용면적 오름차순 ↔ 형 글자 오름차순
    used = set()
    for r in sorted(ok, key=lambda x: (x['danji'], x['m2'])):
        key = norm(r['danji']); tn = tynum(r['ty']) or str(int(r['m2']))
        cands = sorted({(x['danji'], x['ty']) for x in rates if (key in norm(x['danji']) or norm(x['danji']) in key) and tynum(x['ty']).split('.')[0] == tn.split('.')[0] and x['who'] == '청년'})
        cands = [c for c in cands if c not in used]
        if cands:
            c = cands[0]; used.add(c)
            byrank = {x['rank']: x for x in rates if (x['danji'], x['ty']) == c and x['who'] == '청년'}
            s = byrank.get('소계'); r1 = byrank.get('1순위'); r2 = byrank.get('2순위'); r3 = byrank.get('3순위')
            r['rate'] = {'ty': c[1], 'r1': r1 and r1['applicants'], 'r2': r2 and r2['applicants'], 'r3': r3 and r3['applicants'], 'sum': s and s['applicants'], 'rate': s and s['rate'],
                         'r1_fills': bool(r1 and r1['applicants'] >= (r['n'] or 0))}
        elif rd['rates']: r['rate'] = None
    out.append({'id': rd['id'], 'label': rd['label'], 'seq': rd['seq'], 'url': VIEW + rd['seq'], 'posted': rd['posted'], 'apply': rd['apply'], 'total_txt': rd['total_txt'],
                'rates_url': (VIEW + rd['rates_seq']) if rd['rates_seq'] else None,
                'youth_rows': len(youth), 'youth_n': sum((r['n'] or 0) for r in youth), 'small_n': small_n,
                'ok': [{k: v for k, v in r.items() if k != 'page'} for r in ok], 'ok_n': sum(r['n'] or 0 for r in ok),
                'all_rows': len(rows), 'total_n': sum((r['n'] or 0) for r in rows if r['sec'] != '셰어형 예비입주자')})
json.dump({'updated': '2026-10-27', 'source': 'SH 인터넷청약 공고 게시판 — 청년안심주택(공공임대) 입주자 모집공고문 단지표 + 최종 청약경쟁률 PDF (Actions debug-fetch 로 받아 pdfplumber 좌표 파싱)', 'min_m2': MIN, 'rounds': out}, open(sys.argv[1] if len(sys.argv) > 1 else 'ya_notice.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
for rd in out:
    print(rd['label'], 'rows', rd['all_rows'], 'total n', rd['total_n'], '| 청년 rows', rd['youth_rows'], 'n', rd['youth_n'], '| 8평+ rows', len(rd['ok']), 'n', rd['ok_n'], '| 8평 미만 청년', rd['small_n'])
    for r in rd['ok']: print('   ', r['sec'], r['danji'], r['ty'], r['m2'], 'n', r['n'], 'A', r.get('A'), 'rate', r.get('rate'))
