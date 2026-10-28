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
MAX_PAGES = 12       # 단지당 최대 렌더 페이지(평면도·배치도 먼저, 조감도 등은 데이터용으로 뒤에)
WIDTH = 1000         # 기본 렌더 가로 px(조감도 등 데이터용)
HI_WIDTH = 1800      # 평면도(이 사이트 단지의 형)·배치도: 폰에서 확대해도 깨지지 않게 크게
TH_WIDTH = 360       # 카드 가로 스크롤 띠에 쓰는 썸네일

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
  '대치르엘': [('236503', '르엘|대치')],                           # 2021년 1차 신규(르엘대치 …)
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
  '신정이펜하우스 1~5단지': [('98', None)],   # 170823 의 '신정4보금자리지구' 쪽(17~20쪽, 39형)은 신정숲속마을 것
  '신정숲속마을': [('170823', '신정4')],       # 2015 마곡8~12·신정4 국민임대 팸플릿의 신정4지구(39형) 부분
  '상암월드컵파크 9~12단지': [('60', None), ('59', None)],
  '상암월드컵8단지': [('65', None)],                           # '상암 8단지 (국민임대)'(shift_140212_02.pdf) — 2026-10-28 목록 검색 확인
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

# 쪽 직접 지정(쪽 그림을 눈으로 확인한 것) — (단지, seq) → {'keep': [...]} 이면 그 쪽만, {'drop': [...]} 이면 그 쪽은 뺌.
# 여러 단지 묶음 팸플릿은 '히트 + 다음 2쪽' 규칙 때문에 다음 단지 쪽이 끼거나, 머리말이 그림이라 단지를 못 가르는 경우가 있음
# 'kind': {쪽: 'other'|'site'} 는 쪽 성격 고침(목차를 평면도로 잘못 고른 경우 등), 'tys': {쪽: [...]} 는 형 번호 고침
# (쪽 글자 속 치수·계약면적 숫자를 형으로 잘못 읽은 경우 — 고쳐 두면 화면의 면적 필터가 8평 미만 형 평면도를 제대로 뺌)
# 2026-10-28 화면에 뜨는 197장을 전부 열어 보고 정리
PAGE_FIX = {
  ('마포더클래시', '249616'): {'drop': [19, 20]},           # 19·20쪽 = '2022 행복주택 1차 상봉태솔(상봉동 105-97)' 배치도·59형 (2026-10-28 확인)
  ('공덕동 크로시티', '256854'): {'drop': [9],              # 9쪽 = '2022 행복주택 2차 개포자이프레지던스(개포주공4)' 배치도·39형
                                  'kind': {5: 'site'},      # 5쪽 = 단지배치도 + 17A 평면 → 배치도로
                                  'tys': {6: ['17', '18']},   # 6쪽 = 17AS·18A(17~18㎡대, 8평 미만)
                                  'meta': {6: {'code': ['17AS', '18A'], 'tag': []}, 7: {'code': ['18AS', '36A'], 'tag': []}}},   # 7쪽 = 18AS(8세대 주거약자형)·36A(44세대 기본형)
  ('강동리엔파크14단지', '217510'): {'drop': [22],         # 22쪽 = '2020 행복주택 1차 신정동 행복주택' 배치도(총 101세대)
                                    'tys': {19: ['17']},    # 19쪽 = 동호수배치도 + 17A(8평 미만) — 배치도는 18쪽에 있음
                                    'meta': {20: {'code': ['29AS', '36A'], 'tag': []}}},   # 20쪽 = 29AS(63세대)·36A(110세대) 두 형('기본형'은 발코니 비확장 뜻이라 뺌)
  ('강동리엔파크11단지', '217510'): {'tys': {13: ['17'], 14: ['17']},   # 13쪽 = 동호수배치도 + 17A, 14쪽 = 17B·17C (8평 미만)
                                    'meta': {15: {'code': ['29A', '29BS'], 'tag': []}, 16: {'code': ['36A', '36B'], 'tag': []}}},
  # 형 이름(S = 주거약자용)·공급 유형: 쪽 그림에 적힌 그대로(2026-10-28 눈으로 확인). 한 쪽에 두 형이 펼침면으로 실린 것은 둘 다 적음
  ('신내3-4 도시형생활주택', '191854'): {'tys': {17: ['21']},          # 17쪽 = 21A·21AS(21㎡대, 8평 미만)
                                    'meta': {17: {'code': ['21A', '21AS'], 'tag': []}, 18: {'code': ['31A', '31AS'], 'tag': []}}},
  ('천왕이펜하우스8단지', '191854'): {'meta': {22: {'code': ['29A', '29AS'], 'tag': []}, 23: {'code': ['36A', '36AS'], 'tag': []}, 24: {'code': ['45A', '45AS'], 'tag': []}}},
  ('항동 하버라인', '191854'): {'meta': {28: {'code': ['29A', '29AS'], 'tag': []}, 29: {'code': ['39A', '39AS'], 'tag': []}}},
  ('신내 글로리움', '202688'): {'meta': {7: {'code': ['36A', '36AS'], 'tag': []}, 8: {'code': ['36B', '44A'], 'tag': []},
                                         9: {'code': ['44B', '44BS'], 'tag': []}, 10: {'code': ['44CS'], 'tag': ['주거약자형']}}},
  ('천왕연지마을1', '182670'): {'keep': [14, 15, 16, 17],  # 천왕2지구 도시형(1) 32㎡A 32.31·32㎡B 32.64·35㎡A 35.21 — 10~13쪽 20㎡형(6.2평)은 8평 미만, 23~26쪽은 도시형(2)
                                'meta': {14: {'code': ['32A'], 'tag': []}, 15: {'code': ['32B'], 'tag': ['주거약자형']},   # 15쪽 = 32㎡B(주거약자형-16세대), 16쪽 = 32㎡B(31세대)
                                         16: {'code': ['32B'], 'tag': []}, 17: {'code': ['35A'], 'tag': []}}},
  ('천왕연지마을2', '182670'): {'keep': [26]},             # 천왕2지구 도시형(2) 31㎡ 31.06 — 23~25쪽 19·22㎡형은 8평 미만, 10~17쪽은 도시형(1)
  ('푸르내', '256705'): {'tys': {7: ['38']},          # 7쪽 = 38형(전용 38.49) 한 형 — 작은 글자를 59로 잘못 읽어 '59형'으로 붙던 것
                         'meta': {6: {'code': ['28', '28S'], 'tag': []}}},   # 6쪽 = 28(49세대)·28S(12세대 주거약자형)
  ('신정숲속마을', '170823'): {'meta': {19: {'code': ['39A'], 'tag': []},            # 19쪽 = 동호수표(범례에 '39A-S(주거약자형)') + 39A 확장형 204세대
                                        20: {'code': ['39A-S'], 'tag': ['주거약자형']}}},   # 20쪽 = 39A-S 주거약자형 16세대
  ('마곡지구 9단지', '220707'): {'meta': {20: {'code': ['49A', '49AS'], 'tag': []}}},   # 49A(448세대 일반)·49AS(64세대 주거약자)
  ('마곡엠밸리 1~15단지', '170823'): {'drop': [17, 18, 19, 20]},  # 17~20쪽 = 신정4지구(신정숲속마을) 위치도·조감도·39A·39A-S
  # 목차(CONTENTS)·'행복주택이란' 소개 쪽 — 목차에 '39형·26.78㎡' 같은 글자가 있어 평면도로 잘못 잡혔던 쪽
  ('e편한세상 청계센트럴포레', '234861'): {'kind': {2: 'other'}},
  ('목동센트럴아이파크위브', '216153'): {'kind': {2: 'other'}},
  ('아크로타워스퀘어', '185053'): {'kind': {2: 'other'}},
  ('래미안루센티아', '211674'): {'kind': {2: 'other'}},
  ('북한산두산위브', '211671'): {'kind': {2: 'other'}},
  ('왕십리자이', '261091'): {'kind': {2: 'other'}},
  ('서울숲리버뷰자이', '261097'): {'kind': {2: 'other'}},
  ('꿈의숲코오롱하늘채', '185054'): {'kind': {2: 'other'}},
  ('꿈의숲아이파크', '221026'): {'kind': {2: 'other'}},
  ('은뜨락', '256702'): {'kind': {3: 'other'},
                         'tys': {7: ['39'], 8: ['39'], 9: ['39'], 10: ['39'], 11: ['44']},   # 7~10쪽 39A·39A(주거약자)·39B·39B(주거약자), 11쪽 44
                         'meta': {7: {'code': ['39A'], 'tag': []}, 8: {'code': ['39A'], 'tag': ['주거약자형']}, 9: {'code': ['39B'], 'tag': []},
                                  10: {'code': ['39B'], 'tag': ['주거약자형']}, 11: {'code': ['44'], 'tag': []}}},
  # 이든채(신정3 A6BL): 쪽마다 글자에 '39·26'이 같이 있어 전부 '39형'으로 붙던 것 — 쪽 그림의 형 이름대로
  ('래미안베라힐즈', '261086'): {'tys': {3: ['38', '43'], 4: ['43']},     # 3쪽 = 38(기본형 100세대)·43A(확장형 29세대) 두 형, 4쪽 = 43B(기본형 4세대)
                                  'meta': {3: {'code': ['38', '43A']}, 4: {'code': ['43B']}}},   # 큰 형 이름 글자를 못 뽑아 3쪽이 '43형'으로만 붙던 것
  ('이든채', '256703'): {'kind': {3: 'other'},
                         'tys': {7: ['26'], 8: ['26'], 9: ['31'], 10: ['39'], 11: ['39'], 12: ['39'], 13: ['39'], 14: ['44']},   # 26A·26B·31·39A·39AS·39B·39BS·44
                         'meta': {7: {'code': ['26A'], 'tag': []}, 8: {'code': ['26B'], 'tag': []}, 9: {'code': ['31'], 'tag': []},
                                  10: {'code': ['39A'], 'tag': []}, 11: {'code': ['39AS'], 'tag': ['주거약자형']},
                                  12: {'code': ['39B'], 'tag': []}, 13: {'code': ['39BS'], 'tag': ['주거약자형']}, 14: {'code': ['44'], 'tag': []}}},
}
def _fix_ok(name, seq, n):
    f = PAGE_FIX.get((name, str(seq)))
    if not f: return True
    if 'keep' in f: return n in f['keep']
    return n not in f.get('drop', [])
def _fix_page(name, seq, c):
    """PAGE_FIX 의 kind·tys 고침을 후보 쪽(c: {i, kind, tys, meta})에 적용"""
    f = PAGE_FIX.get((name, str(seq))) or {}
    n = c['i'] + 1
    if n in f.get('kind', {}): c['kind'] = f['kind'][n]
    if n in f.get('tys', {}):
        c['tys'] = list(f['tys'][n])
        m = dict(c.get('meta') or {})   # 글자에서 뽑은 전용면적·형 이름도 고친 형 번호에 맞는 것만 남김(화면 필터가 이 값을 먼저 봄)
        if 'ex' in m: m['ex'] = [v for v in m['ex'] if str(int(float(v))) in c['tys']]
        if 'code' in m: m['code'] = [v for v in m['code'] if re.match(r'\d+', v).group(0) in c['tys']]
        c['meta'] = {k: v for k, v in m.items() if v}
    if n in f.get('meta', {}):   # 쪽 그림을 보고 적은 형 이름 등(글자 추출이 못 한 것)
        c['meta'] = dict(c.get('meta') or {}, **f['meta'][n])
    return c

def _cnt(t, keys): return sum(t.count(k) for k in keys)
TY_RE = re.compile(r'(?<!\d)(\d{2})(?:\.\d+)?\s*(?:㎡|m²|㎡형|형|타입|TYPE|Type|[A-D]\b)')
def _kind(t):
    """쪽 성격: plan(평면도) > site(배치도) > other(조감도·교통망·위치도·표지·마감재 등 — 안 씀)"""
    if '평면' in t: return 'plan'
    if '배치도' in t or '단지배치' in t: return 'site'
    return 'other'
def _tys(t):
    out = []
    for m in TY_RE.finditer(t):
        v = m.group(1)
        if 15 <= int(v) <= 90 and v not in out: out.append(v)
    return out
# 평면도 쪽 글자에서 화면 설명용 정보: 정확한 전용면적(29.09) · 형 이름(29A, 29AS) · 공급 유형((기본형)·(주거약자형) 등)
# 예) 2023 행복주택 2차 방화동 19쪽 '29A 85세대(기본형) … 주거전용면적 29.09㎡' (글자는 띄어쓰기를 지운 상태로 들어옴)
EX_RE = re.compile(r'(?:주거)?전용(?:면적)?[:：]?\s*(\d{2,3}\.\d{1,4})')
CODE_RE = re.compile(r'(?<![\d.A-Za-z])(\d{2,3}[A-Z]{1,3})(?=\s*\d{1,4}세대)')
TAG_RE = re.compile(r'\((기본형|일반형|주거약자형|주거약자용|고령자형|고령자용|장애인형|신혼부부형|청년형|대학생형|특화형)\)')
def _meta(t):
    def uniq(it, keep=lambda v: True):
        out = []
        for v in it:
            if keep(v) and v not in out: out.append(v)
        return out
    ex = uniq((m.group(1) for m in EX_RE.finditer(t)), lambda v: 14 <= float(v) <= 120)
    code = uniq(m.group(1) for m in CODE_RE.finditer(t))
    tag = uniq(m.group(1) for m in TAG_RE.finditer(t))
    out = {}
    if ex: out['ex'] = ex[:6]
    if code: out['code'] = code[:4]
    if tag: out['tag'] = tag[:3]
    return out
def pick_pages(pdf, kw, others=()):
    """이 단지 구간의 쪽들을 평면도(plan)·배치도(site)·그 외(other: 조감도·교통망·표지 등) 로 나눠 돌려준다. 화면은 plan/site 만 쓰고 other 는 데이터로만 보관.
    - 키워드 없음(단일 단지 팸플릿): 전체 쪽이 구간
    - 키워드('a|b'): 키워드가 글자로 있고, 같은 팸플릿을 나눠 쓰는 다른 단지 키워드(others)보다 많이 나오는 쪽부터 다음 다른 단지 쪽 전까지가 구간
    반환: ([{i, kind, tys}], 히트 쪽 번호). plan 먼저(형 숫자 있는 쪽 우선), 그다음 site. 최대 MAX_PAGES."""
    n = len(pdf.pages)
    texts = []
    for pg in pdf.pages:
        try: texts.append((pg.extract_text() or '').replace(' ', ''))
        except Exception: texts.append('')
    hits = []
    if not kw:
        section = list(range(n))
    else:
        keys = [k.replace(' ', '') for k in kw.split('|') if k.strip()]
        okeys = [k.replace(' ', '') for o in others for k in o.split('|') if k.strip() and k.replace(' ', '') not in keys]
        mine = [_cnt(t, keys) for t in texts]; theirs = [_cnt(t, okeys) for t in texts]
        hit = [i for i in range(n) if mine[i] > 0 and mine[i] >= theirs[i]]
        strong = [i for i in hit if mine[i] > theirs[i]]
        if okeys and strong: hit = strong
        hits = [h + 1 for h in hit]
        late = [i for i in hit if i >= 3]
        use = late or hit
        if not use: return [], hits
        # 구간 = 첫 히트부터 히트가 이어지는 동안(한 쪽 건너뛰기까지 허용) + 다음 2쪽. 떨어진 히트(목차·바닥글)는 버림
        start = min(use); last = start; useset = set(use)
        j = start
        while j + 1 < n and (j + 1 in useset or j + 2 in useset):
            j += 1
            if j in useset: last = j
        end = min(n, last + 3)
        for k2 in range(start + 1, end):
            if theirs[k2] > mine[k2]: end = k2; break
        section = [i for i in range(start, end) if not (theirs[i] > mine[i])]
    cands = [{'i': i, 'kind': _kind(texts[i]), 'tys': _tys(texts[i]), 'meta': _meta(texts[i])} for i in section]
    for c in cands:   # 목차·공통 유의사항('평면도는 …' 문구 때문에 평면으로 잡히던 쪽)·표지: 형 숫자가 없고 앞 3쪽이거나 목차·유의사항 글자가 있으면 평면도 아님
        t = texts[c['i']]
        if c['kind'] == 'plan' and not c['tys'] and (c['i'] < 3 or re.search(r'유의사항|목차|CONTENTS', t, re.I)): c['kind'] = 'other'
        # 목차 쪽은 '평면도 39형·46형'·'26.78㎡' 처럼 형 숫자가 있어도 평면도가 아님 — 진짜 평면도 쪽엔 '(주거)전용면적 29.09㎡' 같은 글자가 있음
        if c['kind'] == 'plan' and re.search(r'CONTENTS|목차', t, re.I) and not EX_RE.search(t): c['kind'] = 'other'
    plans = [c for c in cands if c['kind'] == 'plan']; sites = [c for c in cands if c['kind'] == 'site']; others = [c for c in cands if c['kind'] == 'other']
    plans.sort(key=lambda c: (0 if c['tys'] else 1, c['i']))
    # 데이터로는 구간 전체(조감도·교통망 포함)를 갖고 있고, 화면에는 plan/site 만 보여준다(kind 로 구분)
    return (plans + sites + others)[:MAX_PAGES], hits

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
    # 사이트 단지별 형(㎡ 정수부) — 그 형의 평면도 쪽은 고해상도로. 국민임대 지구는 39·49·59
    try:
        html = open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
        PLACES = json.loads(re.search(r"var PLACES = (\[.*?\]);\n", html, re.S).group(1))
    except Exception as e:
        PLACES = []; log('PLACES read fail', repr(e))
    TYS = {}
    for pl in PLACES:
        TYS.setdefault(pl['name'], set())
        if pl.get('m2'): TYS[pl['name']].add(str(int(pl['m2'])))
        elif pl.get('kind') == '국민임대': TYS[pl['name']] |= {'39', '49', '59'}
    # PAM 에 없는 PLACES 단지는 팸플릿 목록의 제목·파일명에서 이름으로 찾아 자동 매핑(신정숲속마을처럼 나중에 넣은 단지)
    def _norm(x): return re.sub(r'[\s()\[\]_·,.\-~]', '', x or '')
    for pl in PLACES:
        nm = pl['name']
        if nm in PAM: continue
        key = _norm(re.sub(r'\d+(?:~\d+)?단지|\d+(?:,\d+)*단지|지구', '', nm))[:6]
        hits = [c for c in cat if c.get('seq') and len(key) >= 3 and key in _norm((c.get('title') or '') + ' ' + (c.get('file') or ''))]
        if hits: PAM[nm] = [(h['seq'], key) for h in hits[:2]]; log('auto-mapped', nm, [(h['seq'], h.get('title')) for h in hits[:2]])
        else: log('no pamphlet found for', nm, 'key', key)
    # 같은 쪽을 여러 단지가 쓰면 한 번은 고해상도 조건을 만족할 때 다시 그린다(아래 hi 판정)
    items, rendered, errors = {}, {}, []
    for name, lst in PAM.items():
        ent = []
        for seq, kw in lst:
            try:
                data, fs = get(seq)
                with pdfplumber.open(io.BytesIO(data)) as pdf:
                    others = [k2 for nm2, l2 in PAM.items() for s2, k2 in l2 if s2 == seq and k2 and k2 != kw]
                    sel, hits = pick_pages(pdf, kw, others)
                    sel = [_fix_page(name, seq, c) for c in sel if _fix_ok(name, seq, c['i'] + 1)]
                    pages = []
                    for c in sel:
                        i = c['i']; key = f'{seq}_p{i + 1}'
                        hi = c['kind'] == 'site' or (c['kind'] == 'plan' and (not TYS.get(name) or bool(set(c['tys']) & TYS.get(name, set()))))
                        if key not in rendered or (hi and not rendered[key].get('hi')):
                            pg = pdf.pages[i]
                            width = HI_WIDTH if hi else WIDTH
                            scale = width / float(pg.width)
                            im = pg.to_image(resolution=int(72 * scale)).original.convert('RGB')
                            path = os.path.join(OUTD, key + '.jpg'); im.save(path, 'JPEG', quality=(80 if hi else 72), optimize=True)
                            th = im.copy(); th.thumbnail((TH_WIDTH, TH_WIDTH * 2)); th.save(os.path.join(OUTD, key + '_t.jpg'), 'JPEG', quality=70, optimize=True)
                            rendered[key] = {'img': 'data/pamphlets/' + key + '.jpg', 'th': 'data/pamphlets/' + key + '_t.jpg', 'w': im.width, 'h': im.height, 'hi': hi}
                        pages.append(dict(n=i + 1, kind=c['kind'], tys=c['tys'], **(c.get('meta') if c['kind'] == 'plan' else {}), **rendered[key]))
                    ent.append({'seq': seq, 'title': meta.get(seq, {}).get('title') or (old.get('items', {}).get(name, [{}])[0].get('title') if old else '') or '', 'file': meta.get(seq, {}).get('file', ''),
                                'pdf': f'{DL}?brdId=JI1901&seq={seq}&fileTp=&fileSeq={fs}', 'total': len(pdf.pages), 'kw': kw, 'hits': hits, 'pages': pages})
            except Exception as e:
                log('pamphlet fail', name, seq, repr(e)); errors.append({'name': name, 'seq': seq, 'err': repr(e)[:300]})
        if ent: items[name] = ent
    # 더 이상 안 쓰는 렌더 파일 정리(쪽 선택 규칙이 바뀌면 생김)
    if rendered:
        for fn in os.listdir(OUTD):
            if fn.endswith('.jpg') and re.sub(r'_t$', '', fn[:-4]) not in rendered:
                try: os.remove(os.path.join(OUTD, fn)); log('removed stale', fn)
                except Exception: pass
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y-%m-%d %H:%M KST')
    # 새 행복주택/국민임대 팸플릿(최근 400일) 중 PAM에 없는 것 — 사람이 보고 PAM에 추가하라고 로그·JSON에 남김
    known = {s for lst in PAM.values() for s, _ in lst}
    recent = [c for c in cat if c.get('seq') and c['seq'] not in known and re.search(r'행복주택|국민임대', c.get('title') or '')][:40]
    json.dump({'updated': now, 'source': 'SH 인터넷청약 > 청약정보 > 전자 팸플릿', 'list_url': LIST, 'count': len(cat), 'items': items, 'errors': errors, 'unmapped_recent': recent}, open(OUTJ, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    log('wrote', OUTJ, 'items', len(items), 'pages', len(rendered))

if __name__ == '__main__':
    main()
