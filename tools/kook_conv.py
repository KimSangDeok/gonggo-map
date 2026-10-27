# -*- coding: utf-8 -*-
"""SH 2026 국민임대 공고문(308340) 16~21쪽 '임대금액 전환안내' 표 → data/kook_conv.json
단지·면적마다 기준 임대조건(보증금·월세)과 최대 전환 시 (+) 보증금 최대·월세 최소 / (-) 보증금 최소·월세 최대.
표의 마지막 열(최대 전환 시 월 임대료)은 pdfplumber extract() 에서 빈칸으로 나와서, 행 bbox × 열 x범위로 잘라 글자를 읽는다.
금액: 보증금은 공고문 단위(천원) → 원, 월세는 원.
사용: python tools/kook_conv.py data/sh_files/308340_4_notice.pdf data/kook_conv.json"""
import re, sys, json
import pdfplumber

def _c(s): return re.sub(r'\s+', ' ', (s or '').replace('\x00', ' ').replace('\n', ' ')).strip()
def _rng(s, mul=1):
    nums = [int(x.replace(',', '')) * mul for x in re.findall(r'\d[\d,]*', _c(s))]
    if not nums: return None
    return [min(nums), max(nums)] if len(nums) >= 2 else [nums[0], nums[0]]

def parse(path):
    out, danji, ty, base = [], None, None, None
    with pdfplumber.open(path) as pdf:
        for pi in range(14, min(23, len(pdf.pages))):
            pg = pdf.pages[pi]
            for tb in pg.find_tables():
                ex = tb.extract()
                if not ex or not any('기준 임대 조건' in _c(c) for c in ex[0]): continue
                hdr2 = tb.rows[1].cells
                xr = [c and (c[0], c[2]) for c in hdr2]
                def cell_text(ri, ci):
                    t = _c(ex[ri][ci]) if ci < len(ex[ri]) else ''
                    if t or not xr[ci]: return t
                    # 같은 행의 '최대 전환 보증금' 칸(병합 없음)의 세로 범위로 잘라야 위·아래 행 숫자가 안 섞임
                    ref = tb.rows[ri].cells[7] if len(tb.rows[ri].cells) > 7 and tb.rows[ri].cells[7] else None
                    top, bot = (ref[1], ref[3]) if ref else (tb.rows[ri].bbox[1], tb.rows[ri].bbox[3])
                    return _c(pg.crop((xr[ci][0], top + 0.5, xr[ci][1], bot - 0.5)).extract_text())
                for ri in range(2, len(ex)):
                    r = ex[ri]
                    if _c(r[2]): danji = _c(r[2])
                    if _c(r[3]): ty = _c(r[3])
                    sign = _c(r[6])
                    if sign == '(+)':
                        base = {'dep': _rng(r[4], 1000), 'rent': _rng(r[5])}
                        plus = {'dep': _rng(cell_text(ri, 7), 1000), 'rent': _rng(cell_text(ri, 8))}
                        out.append({'page': pi + 1, 'danji': danji, 'ty': ty, 'base': base, 'plus': plus, 'minus': None})
                    elif sign == '(-)' and out and out[-1]['danji'] == danji and out[-1]['ty'] == ty:
                        out[-1]['minus'] = {'dep': _rng(cell_text(ri, 7), 1000), 'rent': _rng(cell_text(ri, 8))}
    return out

# 지도 PLACES 이름 ↔ 공고문 '지구 및 단지' (공고문 표기 '마곡엠벨리' 그대로)
MAP = [
    ('마곡엠밸리 1~15단지', r'마곡엠[밸벨]리\s*1~15'),
    ('마곡지구 9단지', r'마곡엠[밸벨]리\s*9단지'),
    ('마곡수명산파크 1~7단지', r'마곡수명산파크'),
    ('신정이펜하우스 1~5단지', r'신정이펜하우스'),
    ('신정숲속마을', r'신정4|숲속마을'),
    ('상암월드컵파크 9~12단지', r'상암월드컵파크\s*9~12'),
    ('천왕이펜하우스 1~6단지', r'천왕이펜하우스\s*1~6'),
    ('천왕연지타운 1,2단지', r'천왕연지타운'),
    ('항동하버라인 2·3·4·8단지', r'항동하버라인'),
]

if __name__ == '__main__':
    rows = parse(sys.argv[1])
    res = {}
    for name, pat in MAP:
        hit = [r for r in rows if re.search(pat, r['danji'] or '')]
        res[name] = {r['ty']: {'base': r['base'], 'plus': r['plus'], 'minus': r['minus'], 'page': r['page'], 'danji': r['danji']} for r in hit}
    def sane(r):   # 보증금: (+) > 기준 > (-), 월세: (+) < 기준 < (-) — 범위 양끝 각각
        try:
            b, pl, mi = r['base'], r['plus'], r['minus']
            return all(pl['dep'][i] > b['dep'][i] > mi['dep'][i] and pl['rent'][i] < b['rent'][i] < mi['rent'][i] for i in (0, 1))
        except Exception: return False
    bad = [r for r in rows if not sane(r)]
    json.dump({'source': 'SH 2026년 국민임대주택 입주자모집 공고문(308340) 16~21쪽 「임대금액 전환안내」 — 기준 임대조건과 최대 전환 시 (+)보증금 최대·월세 최소 / (-)보증금 최소·월세 최대',
               'url': 'https://www.i-sh.co.kr/app/lay2/program/S1T294C295/www/brd/m_241/view.do?multi_itm_seqs=1%2C2%2C4%2C8%2C16%2C32%2C64%2C128%2C256&seq=308340',
               'rows_total': len(rows), 'incomplete': len(bad), 'items': res}, open(sys.argv[2], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('rows', len(rows), 'incomplete', len(bad))
    for b in bad[:5]: print('  incomplete:', b)
    for k, v in res.items(): print(k, '->', {t: (x['danji'], x['base'], x['plus'], x['minus']) for t, x in v.items()} if v else 'NOT FOUND')
