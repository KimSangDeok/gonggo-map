# -*- coding: utf-8 -*-
"""공고·단지 데이터 수집기 (GitHub Actions에서 실행). 개인정보 없음.
소스: SH 인터넷청약 공고 게시판, LH 청약플러스 공고 목록, SH 주택정보(houseinfo), K-apt 공동주택관리정보시스템."""
import re, json, datetime, time
import requests
from bs4 import BeautifulSoup

UA = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36 gonggo-map/1.0',
      'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.5'}
S = requests.Session(); S.headers.update(UA)
LOG = []
def log(*a):
    msg = ' '.join(str(x) for x in a); LOG.append(msg); print(msg, flush=True)

# ---------------- SH 공고 게시판 ----------------
SH_BASE = 'https://www.i-sh.co.kr/app/lay2/program/S1T294C295/www/brd/m_241/'
SH_LIST = SH_BASE + 'list.do'
SH_VIEW = SH_BASE + 'view.do?multi_itm_seqs=1%2C2%2C4%2C8%2C16%2C32%2C64%2C128%2C256&seq={seq}'
KEY = re.compile(r'(행복주택|국민임대|통합공공임대|장기전세|청년안심|매입임대|전세임대|재개발임대|영구임대)')
NOTI = re.compile(r'(모집\s*공고|입주자\s*모집|공급\s*공고)')
NOT_NOTICE = re.compile(r'(발표|안내|결과|명단|제출|접수증|지연|일정\s*변경|추가\s*서류|설명회)')

def sh_list(pages=3):
    rows = []
    for page in range(1, pages + 1):
        r = S.get(SH_LIST, params={'page': page}, timeout=40); r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        got = 0
        for tr in soup.find_all('tr'):
            a = None
            for cand in tr.find_all('a'):
                oc = (cand.get('onclick') or '') + ' ' + (cand.get('href') or '')
                if 'getDetailView' in oc or 'seq=' in oc: a = cand; break
            if not a: continue
            oc = (a.get('onclick') or '') + ' ' + (a.get('href') or '')
            m = re.search(r"getDetailView\('?(\d+)'?\)", oc) or re.search(r'seq=(\d+)', oc)
            if not m: continue
            tds = [td.get_text(' ', strip=True) for td in tr.find_all('td')]
            date = next((x for x in tds if re.fullmatch(r'\d{4}[-.]\d{2}[-.]\d{2}', x)), None)
            title = ' '.join(a.get_text(' ', strip=True).split())
            title = re.sub(r'^\[?\s*NEW\s*\]?\s*', '', title, flags=re.I)
            rows.append({'seq': m.group(1), 'title': title, 'date': (date or '').replace('.', '-')}); got += 1
        log(f'SH list page {page}: {got} rows')
        if got == 0:
            first = soup.find('table'); log('SH list sample:', (first.prettify()[:1500] if first else r.text[:800]))
            break
    seen = set(); out = []
    for x in rows:
        if x['seq'] in seen: continue
        seen.add(x['seq']); out.append(x)
    return out

DATE = re.compile(r'(\d{4})\s*[.\-/]\s*(\d{1,2})\s*[.\-/]\s*(\d{1,2})')
PART = re.compile(r'(?<!\d)(\d{1,2})\s*[.\-/]\s*(\d{1,2})(?!\d)')
def _iso(y, m, d): return f'{int(y):04d}-{int(m):02d}-{int(d):02d}'

def extract_steps(text):
    """공고 페이지 본문(텍스트)에서 일정 추출. 라벨 뒤 같은 항목(■/○ 글머리표 전까지) 안의 날짜를 읽는다."""
    labels = [('공고', [r'모집\s*공고\s*일', r'모집\s*공고\s*[(:：]', r'공고\s*일\s*[:：]']), ('접수', [r'인터넷\s*접수', r'접수\s*기간', r'접수\s*일']),
              ('서류심사대상자 발표', [r'서류\s*심사\s*대상자\s*발표']), ('서류 제출', [r'서류\s*제출\s*기간', r'서류\s*제출']),
              ('당첨자 발표', [r'당첨자\s*발표']), ('계약', [r'계약\s*체결\s*기간', r'계약\s*기간', r'계약\s*체결']), ('입주', [r'입주\s*예정\s*(시기|일)', r'입주\s*(시기|일)'])]
    steps = []
    RANGE = re.compile(r'(\d{4})\s*\.\s*(\d{1,2})\s*\.\s*(\d{1,2})\.?\s*(?:\([^)]{1,3}\))?\s*(?:\d{1,2}:\d{2})?\s*[~∼]\s*(\d{4})\s*\.\s*(\d{1,2})\s*\.\s*(\d{1,2})')
    def internet_range():
        for m in RANGE.finditer(text):
            ctx = text[max(0, m.start() - 60): m.start()] + ' ' + text[m.end(): m.end() + 90]
            if '인터넷' in ctx and '방문' not in text[m.end(): m.end() + 40]:
                return [_iso(*m.groups()[:3]), _iso(*m.groups()[3:])]
        return None
    for name, pats in labels:
        got = None
        if name == '접수':
            ir = internet_range()
            if ir: got = ['접수'] + ir
        for pat in ([] if got else pats):
            for m in re.finditer(pat, text):
                seg = text[m.end(): m.end() + 160]
                seg = re.split(r'[■●◎○□▶※]|\n\s*\n', seg)[0]
                full = DATE.findall(seg)
                if not full: continue
                start = _iso(*full[0]); end = None
                parts = re.split(r'[~∼]', seg, 1)
                if len(parts) == 2:
                    f2 = DATE.search(parts[1]); p2 = PART.search(parts[1])
                    if p2 and (not f2 or p2.start() < f2.start()): end = _iso(full[0][0], *p2.groups())
                    elif f2: end = _iso(*f2.groups())
                got = [name, start] + ([end] if end and end != start else [])
                break
            if got: break
        if got: steps.append(got)
    return steps

def sh_view(seq):
    r = S.get(SH_VIEW.format(seq=seq), timeout=40); r.raise_for_status()
    soup = BeautifulSoup(r.text, 'html.parser')
    for s in soup(['script', 'style']): s.decompose()
    cont = soup.select_one('td.cont') or soup.select_one('.bbs_view, .board_view, .view_cont') or soup.body
    text = cont.get_text('\n', strip=True)
    files = re.findall(r'"oriFileNm"\s*:\s*"([^"]+)"', r.text)
    return {'steps': extract_steps(text), 'files': files, 'excerpt': text[:1200]}

def sh_notices(known_seqs):
    rows = sh_list()
    items = []
    for x in rows:
        if not KEY.search(x['title']): continue
        is_notice = bool(NOTI.search(x['title'])) and not NOT_NOTICE.search(x['title'])
        it = dict(x); it['kind'] = '공고' if is_notice else '안내'; it['url'] = SH_VIEW.format(seq=x['seq'])
        it['cat'] = KEY.search(x['title']).group(1)
        if is_notice or x['seq'] in known_seqs:
            try:
                v = sh_view(x['seq']); it.update(v); time.sleep(0.7)
            except Exception as e:
                log('SH view fail', x['seq'], e)
        items.append(it)
    # 기존 공고(지도에 반영된 것)는 목록에 안 보여도 일정 갱신
    for seq in known_seqs:
        if any(i['seq'] == seq for i in items): continue
        try:
            v = sh_view(seq); items.append({'seq': seq, 'title': '', 'date': '', 'kind': '공고', 'url': SH_VIEW.format(seq=seq), **v}); time.sleep(0.7)
        except Exception as e:
            log('SH known view fail', seq, e)
    return items

# ---------------- LH 청약플러스 ----------------
LH_LIST = 'https://apply.lh.or.kr/lhapply/apply/wt/wrtanc/selectWrtancList.do'
LH_INFO = 'https://apply.lh.or.kr/lhapply/apply/wt/wrtanc/selectWrtancInfo.do'
LH_TYPES = ('행복주택', '국민임대', '통합공공임대')
def lh_detail(url):
    """LH 공고 상세 페이지: 단지별 소재지·좌표(var lat_N/lng_N)·세대수·주택형 표·공급일정."""
    r = S.get(url, timeout=60, headers={'Referer': LH_LIST + '?mi=1026'}); r.raise_for_status()
    html = r.text
    lat = dict(re.findall(r'var\s+lat_(\d+)\s*=\s*"([\d.]+)"', html)); lng = dict(re.findall(r'var\s+lng_(\d+)\s*=\s*"([\d.]+)"', html))
    soup = BeautifulSoup(html, 'html.parser')
    comps = []
    for div in soup.select('div[id^=wrtancSbdTab]'):
        idx = div.get('id', '').replace('wrtancSbdTab', '')
        h4 = div.select_one('h4.tit2'); name = h4.get_text(' ', strip=True) if h4 else ''
        info = {}
        for li in div.select('ul.list_st1 li'):
            txt = li.get_text(' ', strip=True)
            if ':' in txt:
                k, v = txt.split(':', 1); info[k.strip()] = v.strip()
        rows = []
        tbl = div.select_one('table')
        if tbl:
            for tr in tbl.select('tbody tr'):
                th = tr.find('th'); tds = tr.find_all('td')
                def cell(td):
                    d = td.find('div'); return (d.get_text(' ', strip=True) if d else td.get_text(' ', strip=True))
                vals = [cell(td) for td in tds]
                if th and len(vals) >= 5:
                    rows.append({'ty': th.get_text(' ', strip=True), 'm2': vals[0], 'n': vals[1], 'dep': vals[2], 'rent': vals[3], 'net': vals[4]})
        comps.append({'name': name, 'addr': info.get('소재지', ''), 'm2': info.get('전용면적(㎡)', ''), 'hh': info.get('총 세대수', ''), 'heat': info.get('난방방식', ''),
                      'movein': info.get('입주예정월', ''), 'lat': float(lat[idx]) if idx in lat else None, 'lng': float(lng[idx]) if idx in lng else None, 'rows': rows})
    text = soup.get_text('\n', strip=True)
    sched = {}
    for key, pat in [('접수', r'접수기간\s*:\s*(\d{4}\.\d{2}\.\d{2})\s*~\s*(\d{4}\.\d{2}\.\d{2})'), ('서류대상자 발표', r'서류제출대상자\s*발표일\s*:\s*(\d{4}\.\d{2}\.\d{2})'),
                     ('서류 접수', r'서류접수기간\s*:\s*(\d{4}\.\d{2}\.\d{2})\s*~\s*(\d{4}\.\d{2}\.\d{2})'), ('당첨자 발표', r'당첨자발표일\s*:\s*(\d{4}\.\d{2}\.\d{2})')]:
        m = re.search(pat, text)
        if m: sched[key] = [g.replace('.', '-') for g in m.groups()]
    return {'complexes': comps, 'sched': sched}

def lh_notices(regions=(('11', '서울특별시'),), days=150):   # 서울만 (경기 제외 — 2026-10-27)
    today = datetime.date.today(); start = today - datetime.timedelta(days=days)
    out = []
    for code, rname in regions:
        data = {'mi': '1026', 'currPage': '1', 'listCo': '100', 'prevListCo': '100', 'srchUppAisTpCd': '061339', 'uppAisTpCd': '06', 'aisTpCd': '', 'srchAisTpCd': '',
                'cnpCd': code, 'panSs': '', 'mvinQf': '', 'schTy': '0', 'startDt': start.isoformat(), 'endDt': today.isoformat(),
                'panStDt': start.strftime('%Y%m%d'), 'panEdDt': today.strftime('%Y%m%d'), 'srchY': 'Y', 'srchFilter': 'N', 'indVal': 'N', 'viewType': '', 'xssChk': 'N', 'csCd': 'CNP_CD', 'minSn': '0', 'maxSn': '100'}
        r = S.post(LH_LIST, data=data, timeout=60, headers={'Referer': LH_LIST + '?mi=1026'}); r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        n = 0
        for tr in soup.select('table tbody tr'):
            a = tr.select_one('a.wrtancInfoBtn')
            if not a: continue
            tds = tr.find_all('td')
            cells = [td.get_text(' ', strip=True) for td in tds]
            ty = cells[1] if len(cells) > 1 else ''
            em = a.find('em'); 
            if em: em.decompose()
            title = ' '.join(a.get_text(' ', strip=True).split())
            dates = [c for c in cells if re.fullmatch(r'\d{4}\.\d{2}\.\d{2}', c)]
            status = next((c for c in cells if c in ('공고중', '접수중', '접수마감', '정정공고중')), '')
            region = cells[3] if len(cells) > 3 else rname
            ids = {k: a.get('data-id' + str(i)) for i, k in ((1, 'panId'), (2, 'ccrCnntSysDsCd'), (3, 'uppAisTpCd'), (4, 'aisTpCd'))}
            url = LH_INFO + '?mi=1026&' + '&'.join(f'{k}={v or ""}' for k, v in ids.items())
            out.append({'src': 'LH', 'type': ty, 'title': title, 'region': region, 'posted': dates[0].replace('.', '-') if dates else '', 'deadline': dates[1].replace('.', '-') if len(dates) > 1 else '', 'status': status, 'url': url, 'panId': ids['panId']}); n += 1
        log(f'LH {rname}: {n} rows (all types)')
        if n == 0: log('LH sample:', r.text[:600])
        time.sleep(1)
    seen = set(); res = []
    for x in out:
        k = x['panId'] + x['title']
        if k in seen: continue
        seen.add(k)
        if any(t in x['type'] for t in LH_TYPES) and '신혼희망' not in x['type']: res.append(x)
    nc = 0
    for x in res:
        try:
            d = lh_detail(x['url']); x['complexes'] = d['complexes']; x['sched'] = d['sched']; nc += len(d['complexes'])
        except Exception as e:
            log('LH detail fail', x['panId'], repr(e))
        time.sleep(0.7)
    log(f'LH details: {len(res)} notices, {nc} complexes')
    return res

# ---------------- SH 주택정보 (houseinfo) ----------------
HI = 'https://www.i-sh.co.kr/houseinfo'
def hi_post(path, params):
    r = S.post(HI + path, data=params, timeout=40, headers={'X-Requested-With': 'XMLHttpRequest', 'Referer': HI + '/main/mainPage.do'})
    try: return r.json()
    except Exception: return {}
def hi_init():
    S.get(HI + '/main/mainPage.do', timeout=40)
def hi_fetch(cd):
    o = {'cd': cd, 'types': [], 'plans': {}}
    sply = hi_post('/map/selectSplyTyInfo.do', {'biznsCd': cd})
    for sp in [x['splyTy'] for x in (sply.get('result') or [])]:
        tag = hi_post('/map/selectHouseHsTyTagInfo.do', {'biznsCd': cd, 'splyTy': sp})
        tl = tag.get('result') or []
        for t in tl:
            d = hi_post('/map/selectHouseHsTyDetailInfo.do', {'biznsCd': cd, 'hsCl': t['hsCl'], 'splyTy': sp})
            r = d.get('result')
            if r: o['types'].append([sp, r.get('hsClNm'), r.get('privuseAr'), r.get('hshdCnt'), r.get('roomNo'), r.get('empthSplyPsblCnt'), r.get('rsrvCount'), r.get('oneyrLaveCnt'), r.get('infoLeasGrtm'), r.get('infoLeasRent'), r.get('stdsYm')])
            il = d.get('imgList') or []
            if il and sp not in o['plans']: o['plans'][sp] = il[0]['imgPath'] + il[0]['imgNewFileNm']
        if not tl:
            d = hi_post('/map/selectSplyTyImgInfo.do', {'biznsCd': cd, 'splyTy': sp}); il = d.get('result') or []
            if il: o['plans'][sp] = il[0]['imgPath'] + il[0]['imgNewFileNm']
    cost = hi_post('/map/selectManaCostInfo.do', {'biznsCd': cd}); cl = cost if isinstance(cost, list) else (cost.get('result') or [])
    if cl: o['kapt'] = cl[0].get('kaptCode'); o['costYm'] = cl[0].get('searchDate'); o['cost'] = [[c.get('prvuseAr'), c.get('manageCost')] for c in cl]
    # 사진 유형 목록(공통코드 SH0175: 01 전경·02 정문·03 배치도·04 단지·05 주차장·06 편의시설·07 실내 각 방·08 기타) — 단지별로 등록된 유형만 돌아옴
    codes = hi_post('/map/selectCmmCdList.do', {'biznsCd': cd, 'cateId': 'SH0175'}); cl2 = codes.get('result') or []
    o['phototypes'] = [c.get('cdNm') for c in cl2 if c.get('cdNm')]
    have = {c.get('cd') for c in cl2}
    o['imgs'] = []
    for ty in ('01', '04', '02'):   # 전경 → 단지 → 정문 순으로 바깥 사진
        if ty not in have and have: continue
        img = hi_post('/map/selectImgList.do', {'biznsCd': cd, 'imgTy': ty}); o['imgs'] = [i['imgPath'] + i['imgNewFileNm'] for i in (img.get('result') or [])[:3]]
        if o['imgs']: break
    if any(c.get('cd') == '07' for c in cl2):
        rm = hi_post('/map/selectImgList.do', {'biznsCd': cd, 'imgTy': '07'})
        o['rooms'] = [[(i.get('imgNm') or '').strip(), i['imgPath'] + i['imgNewFileNm']] for i in (rm.get('result') or [])[:40]]
    mh = hi_post('/map/selectCyberMhInfo.do', {'biznsCd': cd, 'hsCl': ''}); ml = mh.get('result') or []
    if ml: o['cyber'] = [[m.get('splyTy'), m.get('cyberModelhouseUrl')] for m in ml if m.get('cyberModelhouseUrl')]
    f = hi_post('/map/selectHouseFcltDetail.do', {'biznsCd': cd}); o['subway'] = [x['ctgrNm'] + ' ' + x['distance'] for x in (f.get('result') or []) if x.get('ctgrCd') == '1'][:2]
    return o

# ---------------- K-apt ----------------
KAPT = 'https://www.k-apt.go.kr'
_kapt_tok = None
def kapt_init():
    global _kapt_tok
    r = S.get(KAPT + '/web/main/index.do', timeout=40)
    m = re.search(r'name="_csrf"\s+value="([^"]+)"', r.text) or re.search(r'_csrf["\']?\s*[:=]\s*["\']([0-9a-f-]{20,})', r.text)
    _kapt_tok = m.group(1) if m else ''
    log('K-apt token', 'ok' if _kapt_tok else 'MISSING', 'status', r.status_code)
def kapt_fetch(code):
    r = S.post(KAPT + '/kaptinfo/getKaptInfo_detail.do', data={'kaptCode': code, '_csrf': _kapt_tok}, timeout=40,
               headers={'X-Requested-With': 'XMLHttpRequest', 'Referer': KAPT + '/web/main/index.do'})
    d = r.json(); k = d.get('resultMap_kapt') or {}; car = d.get('getKaptdfCarInfo') or {}
    return {'nm': k.get('kaptName'), 'use': k.get('kaptUsedate'), 'dong': k.get('kaptDongCnt'), 'hh': k.get('kaptdaTCnt'), 'heat': k.get('codeHeat'), 'hall': k.get('codeHall'), 'str': k.get('codeStr'),
            'pg': k.get('kaptdPcnt'), 'pu': k.get('kaptdPcntu'), 'cars': car.get('carTot'), 'ev': car.get('carTotEl'), 'elev': k.get('kaptdEcntTotal'), 'cctv': k.get('kaptdCccnt'), 'sale': k.get('codeSale'), 'apt': k.get('codeApt'), 'ctl': k.get('codeCtl')}
