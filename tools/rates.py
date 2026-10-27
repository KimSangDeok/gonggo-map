# -*- coding: utf-8 -*-
"""SH 청약 접수 결과(경쟁률) PDF 파서.
표 머리글 셀의 x좌표 범위로 데이터 셀을 열에 대응시킨다(병합 셀 때문에 pdfplumber 의 열 인덱스가 어긋나는 일이 잦아서).
연도별로 조금씩 다른 표 양식(2021~2026)을 한 파서로 읽고, 결과의 Σ신청 ÷ Σ호수가 게시물 본문의 '최종 경쟁률'과 맞는지로 검증한다.
- 행복주택 행: gu(자치구)·danji(단지)·ty(형)·grp(계층)·kind(우선/일반/예비자)·n(호수)·sum(신청 계)·rate/pri_rate/danji_rate(PDF 경쟁률)
- 국민임대 행: gu·danji·ty(면적)·grp(공급유형)·target(대상)·g(정규화 그룹)·n(모집)·sum(신청자 계)·rate·note"""
import re, io
import pdfplumber

PARSER_VER = 3   # 올리면 update_rates 가 캐시된 PDF 를 다시 파싱

def _n(s):
    return re.sub(r'\s+', ' ', (s or '').replace('\n', ' ')).strip()
NUMRE = re.compile(r'^[\d\s,.]+(?:\s*:\s*1)?$')
def _num(s):
    s = _n(s).replace(' ', '').replace(',', '')
    s = re.sub(r':1$', '', s)
    if not s or s in ('-', '.'): return None
    try: return float(s) if '.' in s else int(s)
    except Exception: return None
def _isnum(s):
    s = _n(s)
    return bool(s) and any(ch.isdigit() for ch in s) and bool(NUMRE.match(s))

HEAD_WORDS = ('단지명', '자치구', '공급대상', '신청자격', '신청 자격', '경쟁률', '모집호수', '공급호수', '지구 및', '지구및', '접수누계', '신청자')
def _is_head(row):
    if any(_isnum(c) for c in row): return False
    t = ' '.join(_n(c) for c in row)
    return any(w in t for w in HEAD_WORDS)

def _field(label, kind):
    raw = label
    l = re.sub(r'[\s()\[\]㎡㎥]', '', label)
    if not l: return None
    if '자치구' in l: return 'gu'
    if '경쟁률' in l:
        if '우선' in l: return 'pri_rate'
        if '단지' in l: return 'danji_rate'
        return 'rate'
    if '소계' in l: return None
    if '단지' in l or '지구' in l: return 'danji'
    has_m2 = ('㎡' in raw) or ('㎥' in raw) or ('면적' in l)
    if kind == 'happy':
        if has_m2 or l in ('형', '주택형'): return 'ty'
        if '자격' in l or '대상' in l or '계층' in l or l == '공급구분': return 'grp'
        if '우선/일반' in l or l in ('분류', '구분', '공급유형', '우선일반'): return 'kind'
        if '공가' in l: return 'vac'
        if '예비' in l: return 'wait'
        if '인터넷' in l: return 'net'
        if '방문' in l: return 'visit'
        if '합계' in l or '호수' in l or '모집세대' in l: return 'total'
        if '신청자' in l or '신청' in l or l.endswith('계') or '누계' in l: return 'sum'
    else:
        if has_m2 or l == '신청유형': return 'ty'
        if '공급유형' in l or '공급구분' in l or l == '구분': return 'grp'
        if l == '대상' or '자격' in l: return 'target'
        if '모집' in l: return 'n'
        if '공가' in l: return 'vac'
        if '예비' in l: return 'wait'
        if '호수' in l or '공급세대' in l: return 'n'
        if '신청자' in l or l.endswith('계'): return 'sum'
        if '비고' in l: return 'note'
    return None

def _blocks(pdf_bytes):
    """표를 (머리글 블록, 데이터 행들) 단위로. 머리글은 키워드 행부터 '숫자 셀이 없는 연속 행'까지. 머리글 없는 다음 페이지 표는 직전 머리글을 이어 쓰고,
    표 중간에 머리글이 다시 나오면(2022 서울리츠 등) 새 블록."""
    heads, data, in_head = [], [], False
    def flush():
        nonlocal data
        if heads and data:
            d = data; data = []; return d
        data = []; return None
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for pg in pdf.pages:
            for tb in pg.find_tables():
                text = tb.extract(); rows = tb.rows
                if not text or not rows: continue
                for i, r in enumerate(text):
                    cells = rows[i].cells if i < len(rows) else []
                    numeric = any(_isnum(c) for c in r)
                    if (_is_head(r) and not in_head) or (in_head and not numeric):
                        if not in_head:
                            d = flush()
                            if d: yield (heads, d)
                            heads = []
                        in_head = True
                        for j, cell in enumerate(cells):
                            if cell is None or j >= len(r): continue
                            t = _n(r[j])
                            if t: heads.append((cell[0], cell[2], i, t))
                        continue
                    in_head = False
                    if not heads: continue
                    rec = {}
                    for j, cell in enumerate(cells):
                        if cell is None or j >= len(r): continue
                        t = _n(r[j])
                        if not t: continue
                        cx = (cell[0] + cell[2]) / 2
                        cont = [h for h in heads if h[0] - 1 <= cx <= h[1] + 1]
                        if not cont: continue
                        minw = min(h[1] - h[0] for h in cont)
                        sel = sorted([h for h in cont if (h[1] - h[0]) <= minw * 3.5], key=lambda h: h[2])  # 상위 머리글(최대 3열 병합)까지 이어 붙임: '모집호수 계' vs '접수누계 계' 구분
                        rec.setdefault(' '.join(h[3] for h in sel), t)
                    if rec: data.append(rec)
    d = flush()
    if d: yield (heads, d)

def _mapped(pdf_bytes, kind):
    for heads, data in _blocks(pdf_bytes):
        rows = []
        for rec in data:
            m = {}
            for lab, t in rec.items():
                f = _field(lab, kind)
                if f and f not in m: m[f] = t
            rows.append(m)
        yield rows

TOTALS = {'계', '총계', '합계', '총합계', '총계(A+B)'}
def _is_total(m):
    return any(isinstance(v, str) and v.replace(' ', '') in TOTALS for v in m.values())
def _grp_norm(g):
    g = _n(g)
    mm = re.search(r'\(([^)]+)\)', g)
    if mm and '행복주택' in g: g = mm.group(1)
    return g.replace('계층', '').replace(' ', '')

def parse_happy(pdf_bytes):
    rows, total = [], None
    gu = danji = ty = grp = None
    for trows in _mapped(pdf_bytes, 'happy'):
        for m in trows:
            kd = (m.get('kind') or '').replace(' ', '')
            labeled = any(m.get(k) for k in ('gu', 'danji', 'ty', 'grp', 'kind'))
            if (_is_total(m) and kd not in ('우선', '일반', '예비자')) or (not labeled and (m.get('sum') or m.get('rate'))):
                total = {'supply': _num(m.get('total')), 'vac': _num(m.get('vac')), 'wait': _num(m.get('wait')), 'sum': _num(m.get('sum')),
                         'rate': _num(m.get('danji_rate') or m.get('rate') or m.get('pri_rate'))}
                continue
            if m.get('gu'): gu = m['gu'].replace(' ', '')
            if m.get('danji'): danji = _n(m['danji'])
            if m.get('ty'): ty = m['ty'].replace(' ', '')
            if m.get('grp'): grp = _grp_norm(m['grp'])
            if kd not in ('우선', '일반', '예비자'):
                continue
            vac, wait, tot, s = _num(m.get('vac')), _num(m.get('wait')), _num(m.get('total')), _num(m.get('sum'))
            rate, pri, dj = _num(m.get('rate')), _num(m.get('pri_rate')), _num(m.get('danji_rate'))
            # 호수(n): 기본은 합계(A+B) 열. 합계가 계층 전체에 세로 병합된 양식(2023 1차)은 행 경쟁률로 판별(신청÷후보 중 PDF 경쟁률과 맞는 것).
            cands = [c for c in (tot, vac, (vac or 0) + (wait or 0)) if c]
            r_chk = rate if rate is not None else (pri if kd == '우선' else None)
            if r_chk and s and cands:
                n = min(cands, key=lambda c: abs(s / c - r_chk))
            else:
                n = tot if tot is not None else (((vac or 0) + (wait or 0)) if (vac is not None or wait is not None) else None)
            rows.append({'gu': gu, 'danji': danji, 'ty': ty, 'grp': grp, 'kind': kd, 'n': n, 'total': tot, 'vac': vac, 'wait': wait,
                         'net': _num(m.get('net')), 'visit': _num(m.get('visit')), 'sum': s, 'rate': rate, 'pri_rate': pri, 'danji_rate': dj})
    return {'total': total, 'rows': rows}

def kook_group(grp, target):
    g = (grp or '') + ' ' + (target or '')
    if '주거약자' in g: return '주거약자'
    if '일반' in g or (grp or '').replace(' ', '') in ('국민임대', '국민임대(50㎡이상)', '국민임대(50㎡초과)'): return '일반'
    if '우선' in g: return '우선공급'
    return (grp or '').strip() or '-'

def parse_kook(pdf_bytes):
    rows, total = [], None
    gu = danji = ty = None
    for trows in _mapped(pdf_bytes, 'kook'):
        for m in trows:
            labeled = any(m.get(k) for k in ('gu', 'danji', 'ty'))
            if _is_total(m) or (not labeled and m.get('sum')):
                total = {'supply': _num(m.get('n')), 'sum': _num(m.get('sum')), 'rate': _num(m.get('rate'))}
                continue
            if m.get('gu'): gu = m['gu'].replace(' ', '')
            if m.get('danji'): danji = _n(m['danji'])
            if m.get('ty'): ty = m['ty'].replace(' ', '')
            if m.get('sum') is None and m.get('n') is None: continue
            n = _num(m.get('n'))
            if n is None and (m.get('vac') or m.get('wait')): n = (_num(m.get('vac')) or 0) + (_num(m.get('wait')) or 0)
            rows.append({'gu': gu, 'danji': danji, 'ty': ty, 'grp': _n(m.get('grp')), 'target': _n(m.get('target')), 'g': kook_group(m.get('grp'), m.get('target')),
                         'n': n, 'vac': _num(m.get('vac')), 'wait': _num(m.get('wait')), 'sum': _num(m.get('sum')), 'rate': _num(m.get('rate')), 'note': _n(m.get('note'))})
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
        if r['ty'] and r['ty'].upper().endswith('S'): continue
        if r['grp'] not in grp_pref: continue
        out.append(r)
    return out
