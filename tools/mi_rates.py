# -*- coding: utf-8 -*-
"""SH 청년 매입임대주택 최종 청약 경쟁률 PDF → 주택별 행 [{sec, gu, addr, name, ty, sex, rank, n, applicants, rate}]"""
import pdfplumber, re, sys, json
LINE = re.compile(r'^(?P<sec>신규공급|재공급)\s+(?P<gu>\S+구)\s+<(?:신규공급|재공급)>\s+\S+구\s+\[(?P<name>[^\]]*)\]\s+\((?P<ty>[^)]*)\)\s+-\s+(?P<addr>.+?)\s+(?P=name)\s+(?P<ty2>\S+)\s+(?P<sex>남성|여성|-)\s+(?P<rank>일반\d순위|소계|우선\S*|\S+순위)\s+(?P<n>\d+)\s+(?P<app>[\d,]+)\s+(?P<rate>[\d,.]+)$')
def parse(path):
    out = []
    with pdfplumber.open(path) as pdf:
        for pi, pg in enumerate(pdf.pages):
            for ln in (pg.extract_text() or '').split('\n'):
                m = LINE.match(ln.strip())
                if not m: continue
                out.append({'page': pi + 1, 'sec': m.group('sec'), 'gu': m.group('gu'), 'name': m.group('name'), 'ty': m.group('ty'), 'addr': m.group('addr'), 'sex': m.group('sex'), 'rank': m.group('rank'), 'n': int(m.group('n')), 'applicants': int(m.group('app').replace(',', '')), 'rate': float(m.group('rate').replace(',', ''))})
    return out
if __name__ == '__main__':
    rows = parse(sys.argv[1]); print(len(rows)); print(json.dumps(rows[:4], ensure_ascii=False))
