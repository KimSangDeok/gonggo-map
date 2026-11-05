# -*- coding: utf-8 -*-
"""공고문 사본 — 알림 대상 공고(data/alerts.json log 의 send=true)의 게시글 본문과 첨부 공고문 PDF 글자를 data/notice_docs/ 에 남김.
왜: 매일 17:30 Claude 요약이 공고 사이트(SH·서울시 청년안심·LH)를 직접 열면 사용자가 매번 '웹사이트 허용'을 눌러야 함(2026-11-05).
    GitHub 러너가 받아 두면 Claude 는 저장소만 읽고 확인함 → 허용 창 없음. 공개 공고만 담음 — 개인정보 없음.
파일: data/notice_docs/<출처>-<번호>.txt (예: ya-6721.txt) — 머리말(제목·주소·게시·접수·받은 시각) → 게시글 본문 → 첨부 공고문(쪽마다 [p.N] = 공고문 N쪽)
      data/notice_docs/index.json — 공고마다 {file, title, url, fetched, pdfs:[{name, pages}], chars, err}
첨부 고르기: 이름에 '공고문'이 든 PDF 먼저(없으면 첫 PDF), 최대 2개 · hwp/hwpx 는 글자를 못 꺼내 이름만 적음
사용: python tools/notice_docs.py [--days 45] [--force] [--key ya:6721 ...]"""
import os, re, io, sys, json, time, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sources import S, SH_VIEW, log
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'notice_docs')
INDEX = os.path.join(OUT, 'index.json')
KST = datetime.timezone(datetime.timedelta(hours=9))
NOW = datetime.datetime.now(KST)
MAX_PDF = 25_000_000      # 첨부 하나 25MB 까지
MAX_CHARS = 150_000       # 사본 하나 15만 자까지(공고문 40쪽쯤)
KEEP_DAYS = 60            # 알림 기록이 이보다 오래된 사본은 지움
SH_DL = 'https://www.i-sh.co.kr/app/com/file/innoFD.do'
YA_HOST = 'https://soco.seoul.go.kr'
LH_HOST = 'https://apply.lh.or.kr'

def load(f, default):
    try: return json.load(open(f, encoding='utf-8'))
    except Exception: return default

def clean(t):
    t = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', t or '')        # PDF 에서 섞여 나오는 제어 문자(grep 이 이진 파일로 봄)
    return re.sub(r'[ \t\u00a0]+', ' ', re.sub(r'\n{3,}', '\n\n', t)).strip()

# 가구원수별 월평균소득 표(도시근로자 소득 기준)의 금액은 사본에서 가림 — 판단엔 '소득 120% 이하' 같은 비율만 쓰고,
# 사이트 규칙상 가구원수별 기준 금액은 공개 파일에 두지 않음. 임대조건 표(보증금 수천만 원·월세 수십만 원)는 그대로 둠
AMT = re.compile(r'\d{1,2},\d{3},\d{3}')
def _inc(a): v = int(a.replace(',', '')); return 3_000_000 <= v < 15_000_000
def mask_income(t):
    out = []
    for ln in t.split('\n'):
        a = [x for x in AMT.findall(ln) if _inc(x)]
        if a and (len(a) >= 2 or re.search(r'소득|가구|%', ln)):
            ln = AMT.sub(lambda m: '○,○○○,○○○' if _inc(m.group(0)) else m.group(0), ln)
        out.append(ln)
    return '\n'.join(out)

def pick(files):
    """files = [(이름, 받는 함수)] → 공고문 PDF 먼저, 최대 2개. 나머지는 이름만"""
    pdf = [f for f in files if f[0].lower().endswith('.pdf')]
    main = [f for f in pdf if '공고문' in f[0] or '모집공고' in f[0]] or pdf[:1]
    rest = [f for f in pdf if f not in main]
    return (main + rest)[:2], [f[0] for f in files if f not in (main + rest)[:2]]

def pdf_text(data):
    import pdfplumber
    pages = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for i, pg in enumerate(pdf.pages, 1):
            try: t = pg.extract_text() or ''
            except Exception as e: t = f'(이 쪽 글자 못 꺼냄: {type(e).__name__})'
            pages.append(f'[p.{i}]\n{clean(t)}')
    return pages

def get_pdf(url, headers=None):
    r = S.get(url, timeout=150, headers=headers or {}); r.raise_for_status()
    if len(r.content) > MAX_PDF: raise RuntimeError(f'첨부가 너무 큼({len(r.content) // 1_000_000}MB)')
    if not r.content.startswith(b'%PDF'): raise RuntimeError(f'PDF 아님({len(r.content)}바이트)')
    return r.content

# ---------- 출처별: 게시글 본문 + 첨부 목록 ----------
def ya_page(url):          # 서울시 청년안심 모집공고 게시판(BMSR00015) 글
    r = S.get(url, timeout=60); r.raise_for_status()
    soup = BeautifulSoup(r.text, 'html.parser')
    box = soup.select_one('div.board_cont') or soup.select_one('#printArea') or soup.body
    body = box.get_text('\n', strip=True) if box else ''
    files = []
    for a in soup.select('span.file a[href*="fileDown.do"]'):
        name = a.get_text(' ', strip=True); href = a.get('href') or ''
        if not name or any(name == f[0] for f in files): continue
        u = href if href.startswith('http') else YA_HOST + href
        files.append((name, (lambda u=u: get_pdf(u, {'Referer': url}))))
    return body, files

def sh_page(seq, url):     # SH 인터넷청약 공고 게시판(m_241) 글 — 첨부는 view.do 의 downList → innoFD.do (update_rates.py 와 같은 방법)
    r = S.get(url or SH_VIEW.format(seq=seq), timeout=60); r.raise_for_status()
    html = r.text
    m = re.search(r'<td[^>]*class="[^"]*cont[^"]*"[^>]*>([\s\S]*?)</td>', html)
    body = BeautifulSoup(m.group(1), 'html.parser').get_text('\n', strip=True) if m else ''
    files = []
    d = re.search(r'downList\s*[:=]\s*(\[[\s\S]*?\])\s*[,;}]', html)
    try: lst = json.loads(d.group(1)) if d else []
    except Exception: lst = []
    for f in lst:
        name = f.get('oriFileNm') or ''
        if not name: continue
        p = {'brdId': f.get('brdId') or 'GS0401', 'seq': f.get('seq') or seq, 'fileTp': 'A', 'fileSeq': f.get('fileSeq') or '1'}
        files.append((name, (lambda p=p: get_pdf(SH_DL + '?' + '&'.join(f'{k}={v}' for k, v in p.items()), {'Referer': SH_VIEW.format(seq=seq)}))))
    return body, files

def lh_page(url):          # LH 청약플러스 공고 상세 — '공고문' 칸의 fileDownLoad('번호') → /lhapply/lhFile.do?fileid=번호
    r = S.get(url, timeout=90, headers={'Referer': LH_HOST + '/lhapply/apply/wt/wrtanc/selectWrtancList.do?mi=1026'}); r.raise_for_status()
    soup = BeautifulSoup(r.text, 'html.parser')
    for s in soup(['script', 'style']): s.decompose()
    box = soup.select_one('div.bbsV_cont') or soup.select_one('#sub_container') or soup.body
    body = box.get_text('\n', strip=True) if box else ''
    files = []
    for dl in soup.select('div.bbsV_atchmnfl dl'):
        dt = dl.find('dt'); lab = dt.get_text(strip=True) if dt else ''
        for a in dl.select('a[href*="fileDownLoad"]'):
            m = re.search(r"fileDownLoad\('(\d+)'\)", a.get('href') or ''); name = a.get_text(' ', strip=True)
            if not m or not name: continue
            if lab == '공고문' and '공고문' not in name: name = '공고문 ' + name
            u = LH_HOST + '/lhapply/lhFile.do?fileid=' + m.group(1)
            files.append((name, (lambda u=u: get_pdf(u, {'Referer': url}))))
    return body, files

def fetch(e):
    key = e['key']; src, _, num = key.partition(':'); url = e.get('url') or ''
    if src == 'ya': body, files = ya_page(url)
    elif src == 'sh': body, files = sh_page(num, url)
    elif src == 'lh': body, files = lh_page(url)
    else: raise RuntimeError('모르는 출처 ' + src)
    use, other = pick(files)
    parts, pdfs, errs = [], [], []
    for name, get in use:
        try:
            pages = pdf_text(get()); time.sleep(0.6)
            parts.append(f'== 첨부 공고문: {name} ({len(pages)}쪽 — [p.N] = 이 파일 N쪽) ==\n' + '\n'.join(pages)); pdfs.append({'name': name, 'pages': len(pages)})
        except Exception as ex:
            errs.append(f'{name}: {ex}'[:200])
    head = '\n'.join([f'공고 key: {key}', f"제목: {e.get('title') or ''}", f'주소: {url}', f"출처: {e.get('src') or ''} · 게시 {e.get('posted') or '?'}" + (f" · 접수 {e['apply']}" if e.get('apply') else ''),
                      f"받은 시각: {NOW.strftime('%Y-%m-%d %H:%M KST')} (GitHub 러너가 공고 사이트에서 받음 — tools/notice_docs.py)",
                      ('받지 않은 첨부(이름만): ' + ' / '.join(other)) if other else '', ('받기 실패: ' + ' / '.join(errs)) if errs else ''])
    txt = clean(head) + '\n(가구원수별 월평균소득 표의 금액은 ○,○○○,○○○ 로 가림 — 공고문 원문 참고)\n\n== 게시글 본문 ==\n' + clean(body)[:20000] + ('\n\n' + '\n\n'.join(parts) if parts else '\n\n(첨부 공고문 PDF 없음 — 본문만)')
    txt = mask_income(txt)
    if len(txt) > MAX_CHARS: txt = txt[:MAX_CHARS] + '\n\n(… 15만 자에서 자름)'
    return txt, pdfs, errs

def main():
    days = 45; force = '--force' in sys.argv; keys = []
    a = sys.argv[1:]
    for i, x in enumerate(a):
        if x == '--days' and i + 1 < len(a): days = int(a[i + 1])
        if x == '--key' and i + 1 < len(a): keys += [k for k in a[i + 1].split(',') if k]
    os.makedirs(OUT, exist_ok=True)
    idx = (load(INDEX, {}) or {}).get('items') or {}
    log_ = (load(os.path.join(ROOT, 'data', 'alerts.json'), {}) or {}).get('log') or []
    cut = (NOW - datetime.timedelta(days=days)).strftime('%Y-%m-%d')
    want = {}
    for e in log_:
        if not e.get('key') or not e.get('url'): continue
        if keys:
            if e['key'] in keys: want[e['key']] = e
        elif e.get('send') and (e.get('at') or '') >= cut: want[e['key']] = e
    done = 0
    for key, e in want.items():
        fn = re.sub(r'[^a-z0-9]+', '-', key.lower()).strip('-') + '.txt'; path = os.path.join(OUT, fn)
        old = idx.get(key) or {}
        if not force and os.path.exists(path) and old.get('pdfs'): continue            # 공고문까지 받은 것은 다시 안 받음
        if not force and old.get('tries', 0) >= 6 and os.path.exists(path): continue    # 첨부가 끝내 안 받아지는 글은 6번까지만
        try:
            txt, pdfs, errs = fetch(e)
            open(path, 'w', encoding='utf-8').write(txt + '\n')
            idx[key] = {'file': 'data/notice_docs/' + fn, 'title': e.get('title') or '', 'url': e.get('url'), 'fetched': NOW.strftime('%Y-%m-%d %H:%M KST'), 'pdfs': pdfs, 'chars': len(txt), 'tries': old.get('tries', 0) + 1, 'err': ' / '.join(errs)[:300]}
            done += 1; log('notice doc', key, len(txt), 'chars', [p['name'] for p in pdfs], errs or '')
        except Exception as ex:
            idx[key] = dict(old, tries=old.get('tries', 0) + 1, err=('받기 실패: ' + repr(ex))[:300], title=e.get('title') or '', url=e.get('url'))
            log('notice doc fail', key, repr(ex)[:200])
        time.sleep(0.8)
    # 정리: 알림 기록이 KEEP_DAYS 넘게 지난 사본은 지움
    recent = {e['key'] for e in log_ if e.get('key') and (e.get('at') or '') >= (NOW - datetime.timedelta(days=KEEP_DAYS)).strftime('%Y-%m-%d')}
    for key in list(idx):
        if key in recent or key in keys: continue
        f = os.path.join(ROOT, idx[key].get('file') or '')
        if idx[key].get('file') and os.path.exists(f): os.remove(f)
        del idx[key]
    idx = dict(sorted(idx.items()))
    json.dump({'about': '알림 대상 공고의 공고문 사본(tools/notice_docs.py, GitHub 러너가 받음) — 매일 Claude 요약이 웹사이트를 열지 않고 이걸로 확인. [p.N] = 첨부 공고문 N쪽',
               'updated': NOW.strftime('%Y-%m-%d %H:%M KST'), 'items': idx}, open(INDEX, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('notice docs: want', len(want), 'fetched', done)

if __name__ == '__main__':
    main()
