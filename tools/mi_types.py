# -*- coding: utf-8 -*-
"""청년 매입임대 모집공고문의 '1. 공급주택' 표(자치구·대상주택(주택명+주소)·총세대수·공급호수·유형·주택형·승강기·주차장)를 읽어
주택별 건물 유형(도시형생활주택/다세대주택/오피스텔/다가구주택 …)·승강기·주차장을 뽑는다. 주택목록 PDF 에는 이 정보가 없어서(주택구조만 있음) 공고문에서 가져온다.
사용: parse(pdf_path) -> [{'gu','name','addr','tot','lift','park','types':[{'n','bld','struct','ty'}]}], key(addr) -> 도로명 주소 키"""
import re, sys, json
import pdfplumber

def _c(s): return re.sub(r'\s+', ' ', (s or '').replace('\x00', ' ').replace('\n', ' ')).strip()
def key(addr):
    """'(강동구 양재대로95길 36-9, 성내동 404-10)' / '서울특별시 강동구 양재대로95길 36-9 (성내동 404-10)' → '강동구양재대로95길36-9'"""
    a = _c(addr).replace('서울특별시', '').replace('서울시', '')
    a = re.sub(r'\(.*?\)', '', a) if a.count('(') and not a.strip().startswith('(') else a.strip().strip('()')
    a = a.split(',')[0]
    return re.sub(r'[\s()\[\]]', '', a)
def lot_key(addr, gu=''):
    """지번으로 2차 매칭: '(강동구 양재대로95길 36-9, 성내동 404-10)' / '서울특별시 강동구 양재대로95길 36-9 (성내동 404-10)' → '강동구성내동404-10'"""
    a = _c(addr)
    m = re.search(r'\(([^()]*?)\)\s*$', a)
    lot = m.group(1) if m and ',' not in m.group(1) else (a.split(',')[-1] if ',' in a else '')
    g = gu or (re.search(r'(\S+구)', a) or [None, ''])[1]
    return re.sub(r'[\s()\[\]]', '', (g or '') + lot.strip(' )'))
def _split_name_addr(cell):
    t = _c(cell)
    m = re.match(r'(.*?)\s*\((.*)$', t)
    if not m: return t, ''
    return m.group(1).strip(' *'), m.group(2).rstrip(')').strip()
def _split_type(cell):
    t = _c(cell)
    m = re.match(r'(.*?)\s*\((.*?)\)\s*$', t)
    return (m.group(1).strip(), m.group(2).strip()) if m else (t, '')

def parse(path):
    houses, cur, gu, bld, struct = [], None, None, '', ''
    with pdfplumber.open(path) as pdf:
        for pg in pdf.pages:
            txt = (pg.extract_text() or '').replace('\x00', ' ')
            if '대상주택' not in txt or '승강기' not in txt: continue
            for tb in pg.find_tables():
                ex = tb.extract()
                if not ex or not any('승강기' in _c(c) for c in ex[0]): continue
                hdr = [_c(c) for c in ex[0]]
                def col(name):
                    for i, h in enumerate(hdr):
                        if name in h.replace(' ', ''): return i
                    return None
                ci = {'tot': col('총세대수'), 'n': col('공급호수'), 'bld': col('유형'), 'ty': col('주택형'), 'lift': col('승강기'), 'park': col('주차장')}
                for r in ex[1:]:
                    r = [(_c(c) if c else '') for c in r] + [''] * (8 - len(r))
                    if r[0] in ('합계', '계', '총계') or r[1] in ('합계', '계'): continue
                    if r[0]: gu = r[0]
                    if r[1]:
                        name, addr = _split_name_addr(r[1])
                        star = r[1].lstrip().startswith('*')   # 공고문 20쪽: 재공급 중 주택명 앞 * = 전세형(월세의 80%까지 보증금 전환)
                        cur = {'gu': gu, 'name': name, 'addr': addr, 'star': star, 'tot': r[ci['tot']] if ci['tot'] is not None else '', 'lift': r[ci['lift']] if ci['lift'] is not None else '', 'park': r[ci['park']] if ci['park'] is not None else '', 'types': []}
                        houses.append(cur); bld = struct = ''
                    if cur is None: continue
                    if ci['bld'] is not None and r[ci['bld']]:
                        bld, struct = _split_type(r[ci['bld']])
                    # 표가 쪽을 넘어가면 승강기/주차장이 뒷 쪽 첫 행에 다시 나오기도 함
                    if not cur['lift'] and ci['lift'] is not None and r[ci['lift']]: cur['lift'] = r[ci['lift']]
                    if not cur['park'] and ci['park'] is not None and r[ci['park']]: cur['park'] = r[ci['park']]
                    if not cur['tot'] and ci['tot'] is not None and r[ci['tot']]: cur['tot'] = r[ci['tot']]
                    ty = r[ci['ty']] if ci['ty'] is not None else ''
                    n = r[ci['n']] if ci['n'] is not None else ''
                    if ty or n:
                        cur['types'].append({'n': n, 'bld': bld, 'struct': struct, 'ty': ty})
    return houses

if __name__ == '__main__':
    hs = parse(sys.argv[1])
    print(len(hs), 'houses')
    import collections
    print(collections.Counter(t['bld'] for h in hs for t in h['types']).most_common())
    print(collections.Counter(h['lift'] for h in hs).most_common())
    for h in hs[:5]: print(json.dumps(h, ensure_ascii=False))
    print('sum n', sum(int(re.sub(r'\D', '', t['n']) or 0) for h in hs for t in h['types']))
