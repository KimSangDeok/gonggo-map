# -*- coding: utf-8 -*-
"""SH 청년 매입임대주택 공고 '주택목록(홈페이지 공개용)' PDF → 호별 행
{no, sec, gu, ho, name, addr, ty(주택형 공개코드), struct, sex, m2(전용), p1:{dep,rent}(1순위 청년), p1s(대학생·취준), p23:{dep,rent}(2~3순위 청년), p23s}"""
import pdfplumber, re, sys, json
MONEY = r'(?:[\d,]+|-)'
LINE = re.compile(r'^(?P<no>\d+)\s+(?P<sec>신규공급|재공급)\s+(?P<gu>\S+?구)\s+(?P<ho>\S+)\s+(?P<name>.+?)\s+(?P<addr>서울특별시\s.+?)\s+(?P<ty>[\dA-Z]+[A-Z]?|-)\s+(?P<struct>[^\d\s]+(?:\s[^\d\s]+)?)\s+(?P<sex>남성|여성|-)\s+(?P<m2>\d+(?:\.\d+)?)\s+(?P<m1>' + MONEY + r')\s+(?P<m2r>' + MONEY + r')\s+(?P<m3>' + MONEY + r')\s+(?P<m4>' + MONEY + r')\s+(?P<m5>' + MONEY + r')\s+(?P<m6>' + MONEY + r')\s+(?P<m7>' + MONEY + r')\s+(?P<m8>' + MONEY + r')$')
def num(s):
    s = (s or '').replace(',', '')
    return int(s) if s.isdigit() else None
def parse(path):
    out = []; bad = []
    with pdfplumber.open(path) as pdf:
        for pi, pg in enumerate(pdf.pages):
            lines = (pg.extract_text() or '').split('\n')
            buf = ''
            for ln in lines:
                ln = ln.strip()
                if re.match(r'^\d+\s+(신규공급|재공급)\s', ln): buf = ln
                elif buf and not re.match(r'^\d+\s+(신규공급|재공급)\s', ln) and not LINE.match(buf): buf += ' ' + ln
                else: continue
                m = LINE.match(buf)
                if m:
                    d = m.groupdict()
                    out.append({'page': pi + 1, 'no': int(d['no']), 'sec': d['sec'], 'gu': d['gu'], 'ho': d['ho'], 'name': d['name'].strip(), 'addr': d['addr'].strip(), 'ty': d['ty'], 'struct': d['struct'].strip(), 'sex': d['sex'], 'm2': float(d['m2']),
                                'p1': {'dep': num(d['m1']), 'rent': num(d['m2r'])}, 'p1s': {'dep': num(d['m3']), 'rent': num(d['m4'])}, 'p23': {'dep': num(d['m5']), 'rent': num(d['m6'])}, 'p23s': {'dep': num(d['m7']), 'rent': num(d['m8'])}})
                    buf = ''
            if buf and not LINE.match(buf): bad.append(buf[:160])
    return out, bad
if __name__ == '__main__':
    rows, bad = parse(sys.argv[1]); print(len(rows), 'bad', len(bad)); [print(' ', b) for b in bad[:10]]
