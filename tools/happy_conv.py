# -*- coding: utf-8 -*-
"""SH 행복주택 공고문 [별표 1] 「임대금액 상세 안내」 → data/happy_conv.json (손으로 실행, 새 공고가 나오면 다시)
단지·공급형·공급구분 줄마다 기준 임대조건(보증금·월세)과 최대 상호전환 시 임대조건 두 가지:
  임대보증금↑ = 월세를 보증금으로 최대 전환(보증금 최대·월세 최소) / 임대보증금↓ = 보증금을 월세로 최대 전환(보증금 최소·월세 최대)
전환 한도·이율은 공고문 '임대 금액 전환 안내'(2026 1차 18쪽 · 2차 17쪽): 보증금→월세 보증금의 50%까지 연 2.5%,
월세→보증금 월세의 50%까지 연 6.0% — 서울리츠1·2호 소유 단지는 둘 다 20%까지.
화면은 사이트의 공고 줄(보증금·월세 숫자)과 이 표의 기준 임대조건이 같은 줄을 찾아 그 줄의 전환 금액을 그대로 보여 줌.
금액: 보증금은 공고문 단위(천원), 월세는 원. 텍스트 추출은 pdftotext -layout(한 줄에 숫자 8개가 나란히 나옴).
사용: python tools/happy_conv.py  (data/sh_files/ 의 공고문 PDF 를 읽음)"""
import re, os, json, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = 'https://www.i-sh.co.kr/app/lay2/program/S1T294C295/www/brd/m_241/view.do?multi_itm_seqs=1%2C2%2C4%2C8%2C16%2C32%2C64%2C128%2C256&seq={}'
NOTICES = [   # (공고 이름, 게시글 seq, PDF, 전환 규칙 쪽)
    ('2026 1차', '304864', 'data/sh_files/304864_1_notice.pdf', 18),
    ('2026 2차', '309337', 'data/sh_files/309337_1_notice.pdf', 17),
]
NUM = re.compile(r'(?<![\d.])\d{1,3}(?:,\d{3})+(?![\d.])')

def parse(pdf):
    txt = subprocess.run(['pdftotext', '-layout', os.path.join(ROOT, pdf), '-'], capture_output=True, text=True, check=True).stdout
    pages = txt.split('\f')
    start = next(i for i, pg in enumerate(pages) if '별표 1' in pg and '임대금액 상세 안내' in pg)
    rows = []
    for i in range(start, len(pages)):
        for line in pages[i].split('\n'):
            v = [int(x.replace(',', '')) for x in NUM.findall(line)]
            if len(v) < 8: continue
            d0, c, b, r0, du, ru, dd, rd = v[-8:]
            if c + b != d0: continue   # 계약금 + 잔금 = 보증금 계 인 줄만(다른 표 숫자 섞임 방지)
            rows.append({'page': i + 1, 'base': [d0, r0], 'up': [du, ru], 'down': [dd, rd],
                         'pct': [round(100 * (1 - ru / r0)), round(100 * (1 - dd / d0))], 'line': re.sub(r'\s+', ' ', line.strip())[:120]})
    return rows, start + 1

def main():
    out = {'source': 'SH 행복주택 입주자모집 공고문 [별표 1] 임대금액 상세 안내 — 기준 임대조건과 최대 상호전환 시(임대보증금↑ / 임대보증금↓)',
           'rule': '보증금→월세: 보증금의 50%까지 연 2.5% · 월세→보증금: 월세의 50%까지 연 6.0% · 서울리츠1·2호 소유 단지는 둘 다 20%까지',
           'notices': {}}
    for name, seq, pdf, rule_pg in NOTICES:
        rows, p0 = parse(pdf)
        out['notices'][name] = {'seq': seq, 'url': URL.format(seq), 'rule_page': rule_pg, 'table_page': p0, 'rows': rows}
        print(name, 'rows', len(rows), 'from page', p0)
    json.dump(out, open(os.path.join(ROOT, 'data', 'happy_conv.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)

if __name__ == '__main__':
    main()
