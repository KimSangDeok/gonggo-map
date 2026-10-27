# -*- coding: utf-8 -*-
"""SH 전자팸플릿(청약정보 > 전자 팸플릿, 게시판 m_134 / brdId JI1901) PDF를 받아 단지별 해당 페이지를 JPG로 렌더링.
- 목록: list.do?page=N (10건/쪽, 2026-10 기준 58쪽 572건) 의 initParam.downList 에 seq/파일명이 들어 있음
- 다운로드: GET /app/com/file/innoFD.do?brdId=JI1901&seq=<seq>&fileTp=&fileSeq=1 (Innorix 없이 바로 받아짐, 직접 확인)
- 단지 ↔ 팸플릿 대응은 PAM 표(수동 확인). 여러 단지를 묶은 팸플릿은 페이지 글자에 키워드가 있는 쪽만 고름.
출력: data/pamphlets/<seq>_p<N>.jpg, data/pamphlets.json"""
import os, re, io, sys, json, time, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sources import S, log
import pdfplumber

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTD = os.path.join(ROOT, 'data', 'pamphlets'); OUTJ = os.path.join(ROOT, 'data', 'pamphlets.json')
LIST = 'https://www.i-sh.co.kr/app/lay2/program/S48T582C583/www/brd/m_134/list.do'
DL = 'https://www.i-sh.co.kr/app/com/file/innoFD.do'
MAX_PAGES = 8        # 단지당 최대 렌더 페이지
WIDTH = 1000         # 렌더 가로 px

# 단지(사이트의 pick 이름) → [(팸플릿 seq, 페이지 고르는 키워드 또는 None=전체)]. 2026-10-27 전자팸플릿 목록(572건)에서 대조.
PAM = {
  '방화스카이포레': [('269197', '방화')],                       # 2023년 2차 행복주택 신규 공급 단지(방화동 행복주택 …)
  '이문 아이파크 자이': [('290229', None)],
  'e편한세상 청계센트럴포레': [('234861', None)],              # 용두5
  '목동센트럴아이파크위브': [('216153', None)],
  '이든채': [('256703', None)],
  '아크로타워스퀘어': [('185053', None)],
  '천왕이펜하우스8단지': [('191854', '천왕')],                  # 2018년 1차 건설형(천왕8단지 …)
  '항동 하버라인': [('191854', '항동')],
  '천왕이펜하우스7': [('166099', '천왕')],                      # 2015 행복주택(강일11, 천왕7, 내곡)
  '천왕연지마을1': [('182670', '천왕')],                        # 2017년 1차(천왕연지마을1·2, 신내3-3)
  '천왕연지마을2': [('182670', '천왕')],
  '마포더클래시': [('249616', '마포더클래시')],                  # 2022년 1차 신규
  '공덕동 크로시티': [('256854', '크로시티')],                   # 2022년 2차 신규
  '마포자이더센트리지': [('256706', None)],
  'e편한세상신촌': [('182672', None)],
  '홍제센트럴아이파크': [('261103', None)],
  '래미안루센티아': [('211674', None)],
  '힐스테이트신촌': [('221031', None)],
  '북한산두산위브': [('211671', None)],
  '대치르엘': [('236503', '르엘')],                              # 2021년 1차 신규(르엘대치 …)
  '고덕온빛채': [('275456', '고덕강일')],                        # 2024년 1차 신규(고덕강일 2BL = 고덕온빛채)
  '강동리엔파크14단지': [('217510', '14단지')],                  # 2020년 1차 공사건설형
  '강동리엔파크11단지': [('217510', '11단지')],
  '푸르내': [('256705', None)],
  '왕십리자이': [('261091', None)],
  '서울숲리버뷰자이': [('261097', None)],
  '꿈의숲코오롱하늘채': [('185054', None)],
  '래미안길음센터피스': [('261087', None)],
  '꿈의숲아이파크': [('221026', None)],
  '보문파크뷰자이': [('182671', None)],
  '장위자이레디언트': [('282722', None)],
  '창경궁롯데캐슬시그니처': [('309298', None)],
  '송파시그니처롯데캐슬': [('244363', None)],
  'e편한세상송파파크센트럴': [('221028', None)],
  '용산롯데캐슬센터포레': [('256709', None)],
  '용산센트럴파크 헤링턴스퀘어': [('216159', None)],
  '경희궁자이': [('185065', None)],
  '신내 글로리움': [('202688', None)],                          # 2019년 1차(신내글로리움)
  '신내3-3 도시형생활주택': [('182670', '신내')],
  '신내3-4 도시형생활주택': [('191854', '신내')],
  '래미안베라힐즈': [('261086', None)],
  '은뜨락': [('256702', None)],
  '힐스테이트녹번역': [('234863', None)],                       # 응암1
  '백련산해모로': [('216154', None)],
  'DMCSK뷰': [('244364', None)],
  # 국민임대 지구(옛 팸플릿이지만 평면도·배치도가 있음)
  '마곡엠밸리 1~15단지': [('170823', None), ('144', None)],     # 마곡8~12·신정4 국민임대(2015), 마곡1~5 국민임대(2013)
  '마곡지구 9단지': [('220707', '마곡')],                        # 2020년 2차 국민임대(고덕강일8,14, 마곡9)
  '마곡수명산파크 1~7단지': [('252', None), ('164890', None)],  # 발산지구, 발산지구 7단지
  '신정이펜하우스 1~5단지': [('170823', '신정'), ('98', None)],
  '상암월드컵파크 9~12단지': [('60', None), ('59', None)],
  '천왕이펜하우스 1~6단지': [('115', None), ('171094', None)],
  '천왕연지타운 1,2단지': [('105', None)],
  '항동하버라인 2·3·4·8단지': [('199423', None), ('193300', None)],
}

def catalog(pages=60):
    """전자팸플릿 목록 전체(제목·파일명·seq) — 새 팸플릿 감지용."""
    out = []
    for p in range(1, pages + 1):
        r = S.get(LIST, params={'page': p, 'srchWord': '', 'srchTp': '', 'itm_seq_1': 0, 'multi_itm_seq': 0}, timeout=40); r.raise_for_status()
        m = re.search(r'downList\s*[:=]\s*(\[[\s\S]*?\])\s*[,;}]', r.text)
        lst = json.loads(m.group(1)) if m else []
        titles = re.findall(r'<td class="txtL"[^>]*>[\s\S]*?onclick="existFile\(\'(\d+)\'\)[^>]*>\s*([^<]+?)\s*</a>', r.text)
        tmap = {int(i): t.strip() for i, t in titles}
        for i, f in enumerate(lst): out.append({'seq': f.get('seq'), 'file': f.get('oriFileNm'), 'title': tmap.get(i, ''), 'fileSeq': f.get('fileSeq') or '1', 'brdId': f.get('brdId') or 'JI1901'})
        if not lst: break
        time.sleep(0.3)
    return out

def download(seq, file_seq='1', brd='JI1901'):
    """게시물마다 fileSeq가 1·2·3으로 다르다(목록 downList 값). 모르면 1→2→3 순으로 시도."""
    last = None
    tries = [file_seq] + [x for x in ('1', '2', '3') if x != file_seq]
    for fs in tries:
        for attempt in range(2):
            try:
                r = S.get(DL, params={'brdId': brd, 'seq': seq, 'fileTp': '', 'fileSeq': fs}, timeout=300, headers={'Referer': LIST})
                if r.status_code == 500: last = RuntimeError(f'500 fileSeq={fs}'); break
                r.raise_for_status()
                if not r.content.startswith(b'%PDF'): raise RuntimeError(f'not pdf: {r.content[:40]!r}')
                return r.content, fs
            except Exception as e:
                last = e; time.sleep(3)
    raise last

def pick_pages(pdf, kw):
    """키워드 없는 단일 단지 팸플릿: 앞에서부터 MAX_PAGES 쪽. 묶음 팸플릿: 키워드가 글자로 들어 있는 쪽(+다음 2쪽).
    앞 3쪽(표지·목차)에도 키워드가 있기 마련이라 뒤쪽에 다른 히트가 있으면 앞 3쪽은 뺀다. 반환: (선택 쪽 인덱스, 히트 쪽 번호)"""
    n = len(pdf.pages)
    if not kw: return list(range(min(n, MAX_PAGES))), []
    k = kw.replace(' ', '')
    hit = []
    for i, pg in enumerate(pdf.pages):
        try: t = (pg.extract_text() or '').replace(' ', '')
        except Exception: t = ''
        if k in t: hit.append(i)
    if not hit: return list(range(min(n, 3))), []
    late = [i for i in hit if i >= 3]
    use = late or hit
    sel = []
    for i in use:
        for j in (i, i + 1, i + 2):
            if j < n and j not in sel: sel.append(j)
    return sel[:MAX_PAGES], [h + 1 for h in hit]

def main():
    os.makedirs(OUTD, exist_ok=True)
    old = {}
    if os.path.exists(OUTJ):
        try: old = json.load(open(OUTJ, encoding='utf-8'))
        except Exception: old = {}
    try: cat = catalog()
    except Exception as e: cat = []; log('catalog fail', repr(e))
    meta = {c['seq']: c for c in cat if c.get('seq')}
    log('pamphlet catalog:', len(cat))
    pdfs = {}
    def get(seq):
        if seq not in pdfs:
            m = meta.get(seq, {})
            data, fs = download(seq, m.get('fileSeq') or '1', m.get('brdId') or 'JI1901'); pdfs[seq] = (data, fs); time.sleep(0.5); log('downloaded', seq, 'fileSeq', fs, len(data))
        return pdfs[seq]
    items, rendered, errors = {}, {}, []
    for name, lst in PAM.items():
        ent = []
        for seq, kw in lst:
            try:
                data, fs = get(seq)
                with pdfplumber.open(io.BytesIO(data)) as pdf:
                    sel, hits = pick_pages(pdf, kw)
                    pages = []
                    for i in sel:
                        key = f'{seq}_p{i + 1}'
                        if key not in rendered:
                            pg = pdf.pages[i]
                            scale = WIDTH / float(pg.width)
                            im = pg.to_image(resolution=int(72 * scale)).original.convert('RGB')
                            path = os.path.join(OUTD, key + '.jpg'); im.save(path, 'JPEG', quality=72, optimize=True)
                            rendered[key] = {'img': 'data/pamphlets/' + key + '.jpg', 'w': im.width, 'h': im.height}
                        pages.append(dict(n=i + 1, **rendered[key]))
                    ent.append({'seq': seq, 'title': meta.get(seq, {}).get('title') or (old.get('items', {}).get(name, [{}])[0].get('title') if old else '') or '', 'file': meta.get(seq, {}).get('file', ''),
                                'pdf': f'{DL}?brdId=JI1901&seq={seq}&fileTp=&fileSeq={fs}', 'total': len(pdf.pages), 'kw': kw, 'hits': hits, 'pages': pages})
            except Exception as e:
                log('pamphlet fail', name, seq, repr(e)); errors.append({'name': name, 'seq': seq, 'err': repr(e)[:300]})
        if ent: items[name] = ent
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y-%m-%d %H:%M KST')
    # 새 행복주택/국민임대 팸플릿(최근 400일) 중 PAM에 없는 것 — 사람이 보고 PAM에 추가하라고 로그·JSON에 남김
    known = {s for lst in PAM.values() for s, _ in lst}
    recent = [c for c in cat if c.get('seq') and c['seq'] not in known and re.search(r'행복주택|국민임대', c.get('title') or '')][:40]
    json.dump({'updated': now, 'source': 'SH 인터넷청약 > 청약정보 > 전자 팸플릿', 'list_url': LIST, 'items': items, 'errors': errors, 'unmapped_recent': recent}, open(OUTJ, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    log('wrote', OUTJ, 'items', len(items), 'pages', len(rendered))

if __name__ == '__main__':
    main()
