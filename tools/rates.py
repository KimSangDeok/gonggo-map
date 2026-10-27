# -*- coding: utf-8 -*-
"""SH 청약 접수 결과(경쟁률) PDF 파서. 행복주택: 자치구/단지/형/계층/우선·일반 행. 국민임대: 자치구/단지/면적/공급유형 행."""
import re, io
import pdfplumber

def _n(s):
    s = (s or '').replace('\n', ' ').strip()
    return s
def _num(s):
    s = _n(s).replace(',', '')
    try: return float(s) if '.' in s else int(s)
    except Exception: return None

def parse_happy(pdf_bytes):
    """returns {'total': {...}, 'rows': [ {gu,danji,ty,grp,kind,total,vac,wait,net,visit,sum,pri_rate,danji_rate} ]}"""
    rows, total = [], None
    gu = danji = ty = grp = None
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for pg in pdf.pages:
            for t in pg.extract_tables() or []:
                for r in t:
                    c = [_n(x) for x in r]
                    if len(c) < 13 or c[0] in ('자치구',) or (c[0] == '' and c[5] in ('', '합계 (A+B)', '합계')): continue
                    if c[0] == '계':
                        total = {'supply': _num(c[5]), 'vac': _num(c[6]), 'wait': _num(c[7]), 'sum': _num(c[10]), 'rate': _num(c[12])}; continue
                    if c[0]: gu = c[0]
                    if c[1]: danji = c[1]
                    if c[2]: ty = c[2]
                    if c[3]: grp = c[3]
                    kind = c[4]
                    if kind not in ('우선', '일반', '예비자'): continue
                    rows.append({'gu': gu, 'danji': danji, 'ty': ty, 'grp': grp, 'kind': kind, 'total': _num(c[5]), 'vac': _num(c[6]), 'wait': _num(c[7]),
                                 'net': _num(c[8]), 'visit': _num(c[9]), 'sum': _num(c[10]), 'pri_rate': _num(c[11]), 'danji_rate': _num(c[12])})
    return {'total': total, 'rows': rows}

def parse_kook(pdf_bytes):
    rows, total = [], None
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for pg in pdf.pages:
            for t in pg.extract_tables() or []:
                for r in t:
                    c = [_n(x) for x in r]
                    if len(c) < 7 or c[0] == '자치구': continue
                    if c[0].replace(' ', '') == '총계':
                        total = {'supply': _num(c[4]), 'sum': _num(c[5]), 'rate': _num(c[6])}; continue
                    if not c[1]: continue
                    rows.append({'gu': c[0], 'danji': c[1], 'ar': c[2], 'sply': c[3], 'n': _num(c[4]), 'sum': _num(c[5]), 'rate': _num(c[6]), 'note': c[7] if len(c) > 7 else ''})
    return {'total': total, 'rows': rows}

def norm(s): return re.sub(r'[\s()\[\]_·,.\-]', '', s or '').lower()

def happy_rows_for(rows, name, m2, grp_pref=('청년', '대학생')):
    """단지명·형 매칭: 단지명은 공백/괄호 제거 후 포함 관계, 형은 정수부 일치(S형 제외)."""
    key = norm(name); base = str(int(m2)) if m2 else None  # SH 형 명칭은 전용면적 정수부(36.87㎡ → 36형)
    out = []
    for r in rows:
        dn = norm(r['danji'])
        if not (key in dn or dn in key or key[:6] in dn): continue
        if base and re.sub(r'[^0-9]', '', r['ty'] or '') != base: continue
        if r['ty'] and r['ty'].endswith('S'): continue
        if r['grp'] not in grp_pref: continue
        out.append(r)
    return out
