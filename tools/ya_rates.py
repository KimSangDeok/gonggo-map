# -*- coding: utf-8 -*-
"""SH 청년안심주택(공공임대) 최종 청약경쟁률 PDF → 행 [{danji, ty, who, rank, applicants, rate, n(=신청자÷경쟁률)}]"""
import pdfplumber, re, sys, json
LINE = re.compile(r'^(?P<name>.+?)\s+(?P<ty>\d{2}(?:\.\d+)?[A-Z]?(?:\([^)]*\))?|\d{2}[MW])\s+(?P<who>청년(?:\([^)]*\))?|신혼[ⅠⅡI]+|대학생|고령자)\s+(?P<rank>\d순위|소계)\s+(?:(?P<n>\d+)\s+)?(?P<app>[\d,]+)\s+(?P<rate>[\d.]+)$')
def parse(path):
    out = []
    with pdfplumber.open(path) as pdf:
        for pi, pg in enumerate(pdf.pages):
            for ln in (pg.extract_text() or '').split('\n'):
                m = LINE.match(ln.strip())
                if not m: continue
                app = int(m.group('app').replace(',', '')); rate = float(m.group('rate'))
                n = int(m.group('n')) if m.group('n') else (round(app / rate) if rate > 0 else None)
                out.append({'page': pi + 1, 'danji': m.group('name').strip(), 'ty': m.group('ty'), 'who': m.group('who'), 'rank': m.group('rank'), 'applicants': app, 'rate': rate, 'n': n})
    return out
if __name__ == '__main__':
    rows = parse(sys.argv[1])
    print(len(rows)); print(json.dumps(rows[:8], ensure_ascii=False))
