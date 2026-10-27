# -*- coding: utf-8 -*-
"""SH 공고 게시판에서 지난 공고의 청약 접수 결과(경쟁률) 게시물을 찾아 첨부 PDF를 내려받고 표를 파싱해 data/rates.json 에 저장.
- 검색: list.do POST (srchTp=0 제목, srchWord='경쟁률' / '접수결과' / '접수 결과')
- 대상: 행복주택·국민임대 결과 게시물(2021년 이후)
- 첨부: view.do 의 downList(brdId/seq/fileSeq) → innoFD.do 로 직접 GET (Innorix 에이전트 불필요)
- PDF 는 data/sh_files/<seq>_<fileSeq>.pdf 에 캐시(재파싱 가능), 파싱 결과는 posts[seq] 에 누적.
실행: python tools/update_rates.py [--all]  (--all: 이미 파싱된 게시물도 다시 파싱)"""
import os, re, sys, json, time, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sources import S, log, SH_LIST, SH_VIEW
import rates

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'rates.json')
FILES = os.path.join(ROOT, 'data', 'sh_files')
DL = 'https://www.i-sh.co.kr/app/com/file/innoFD.do'
SINCE = '2021-01-01'

def search(word, pages=4):
    out = []
    for page in range(1, pages + 1):
        r = S.post(SH_LIST, data={'page': page, 'seq': '', 'multi_itm_seq': '0', 'multi_itm_seqsStr': '', 'srchTp': '0', 'srchWord': word}, timeout=40)
        r.raise_for_status()
        got = 0
        for m in re.finditer(r'<tr[\s\S]*?</tr>', r.text):
            tr = m.group(0)
            s = re.search(r"getDetailView\('?(\d+)'?\)", tr) or re.search(r'seq=(\d+)', tr)
            if not s: continue
            a = re.search(r'<a[^>]*>([\s\S]*?)</a>', tr)
            title = ' '.join(re.sub(r'<[^>]+>', ' ', a.group(1) if a else '').split())
            dates = re.findall(r'(\d{4})[-.](\d{2})[-.](\d{2})', re.sub(r'<[^>]+>', ' ', tr))
            date = dates[-1] if dates else None   # 마지막 날짜 = 등록일 열(제목 안의 공고일이 먼저 나옴)
            out.append({'seq': s.group(1), 'title': title, 'date': '-'.join(date) if date else ''}); got += 1
        log(f'SH search {word!r} page {page}: {got}')
        if got < 10: break
        time.sleep(0.5)
    return out

def classify(title):
    t = title.replace(' ', '')
    res = ('경쟁률' in t) or ('접수결과' in t)
    if not res: return None
    if '행복주택' in t: return 'happy'
    if '국민임대' in t: return 'kook'
    return None

def label_of(title, kind):
    y = re.search(r'(20\d{2})\s*년', title)
    rnd = re.search(r'(?:제\s*)?(\d)\s*차', title)
    word = '서울리츠 행복' if '서울리츠' in title else ('행복' if kind == 'happy' else '국민임대')
    parts = [y.group(1) if y else '', (rnd.group(1) + '차') if rnd else '', word]
    return ' '.join(p for p in parts if p)

def body_total(text):
    """본문에서 '최종 경쟁률 : 42.2 : 1 (1,484세대 공급, 총 62,635명 신청)' / '총 청약 경쟁률 32 : 1' 추출."""
    m = re.search(r'경쟁률\s*[:：]?\s*([\d.]+)\s*[:：]\s*1(?:\s*\(\s*([\d,]+)\s*(?:세대|호)[^,)]*,\s*총\s*([\d,]+)\s*명)?', text)
    if not m: return None
    out = {'rate': float(m.group(1))}
    if m.group(2): out['supply'] = int(m.group(2).replace(',', ''))
    if m.group(3): out['sum'] = int(m.group(3).replace(',', ''))
    return out

def view(seq):
    r = S.get(SH_VIEW.format(seq=seq), timeout=40); r.raise_for_status()
    html = r.text
    m = re.search(r'downList\s*[:=]\s*(\[[\s\S]*?\])\s*[,;}]', html)
    files = []
    if m:
        try: files = json.loads(m.group(1))
        except Exception as e: log('downList parse fail', seq, e)
    body = re.search(r'<td[^>]*class="[^"]*cont[^"]*"[^>]*>([\s\S]*?)</td>', html)
    text = re.sub(r'<[^>]+>', ' ', body.group(1) if body else '')
    text = ' '.join(re.sub(r'&nbsp;|&#160;', ' ', text).split())
    return files, text

def download(seq, file_seq, brd='GS0401'):
    os.makedirs(FILES, exist_ok=True)
    path = os.path.join(FILES, f'{seq}_{file_seq}.pdf')
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        return path
    r = S.get(DL, params={'brdId': brd, 'seq': seq, 'fileTp': 'A', 'fileSeq': file_seq}, timeout=90, headers={'Referer': SH_VIEW.format(seq=seq)})
    r.raise_for_status()
    if not r.content.startswith(b'%PDF'):
        raise RuntimeError(f'not a PDF ({len(r.content)} bytes): {r.content[:60]!r}')
    with open(path, 'wb') as f: f.write(r.content)
    log('downloaded', path, len(r.content))
    return path

def main(reparse=False, offline=False):
    old = {}
    if os.path.exists(OUT):
        try: old = json.load(open(OUT, encoding='utf-8')).get('posts', {})
        except Exception: old = {}
    found = {}
    if offline:   # 네트워크 없이 캐시된 PDF 만 다시 파싱(파서 개발용)
        for seq, p in old.items(): found[seq] = {'seq': seq, 'title': p['title'], 'date': p['date'], 'kind': p['kind']}
    for w in (() if offline else ('경쟁률', '접수결과', '접수 결과')):
        try:
            for x in search(w):
                k = classify(x['title'])
                if k and x['date'] >= SINCE: found[x['seq']] = dict(x, kind=k)
        except Exception as e:
            log('search fail', w, e)
    log('result posts found:', len(found))
    posts = dict(old)
    for seq, x in sorted(found.items(), key=lambda kv: kv[1]['date'], reverse=True):
        if not reparse and seq in old and old[seq].get('rows') and old[seq].get('pv') == rates.PARSER_VER:
            if not offline and x.get('date'): posts[seq]['date'] = x['date']; posts[seq]['title'] = x['title']; posts[seq]['label'] = label_of(x['title'], x['kind'])
            continue
        try:
            if offline:
                files = [{'fileSeq': f['fileSeq'], 'oriFileNm': f['name'], 'fileSize': f['size']} for f in old[seq]['files']]; text = ''
            else:
                files, text = view(seq); time.sleep(0.6)
            pdfs = [f for f in files if (f.get('oriFileNm') or '').lower().endswith('.pdf')]
            rows, total = [], None
            parsed_files = []
            for f in pdfs:
                path = download(seq, f['fileSeq'], f.get('brdId') or 'GS0401'); time.sleep(0 if offline else 0.6)
                data = open(path, 'rb').read()
                res = rates.parse_happy(data) if x['kind'] == 'happy' else rates.parse_kook(data)
                rows += res['rows']
                if res.get('total') and not total: total = res['total']
                parsed_files.append({'fileSeq': f['fileSeq'], 'name': f.get('oriFileNm'), 'size': int(f.get('fileSize') or 0), 'rows': len(res['rows'])})
            # 단지명 열이 없는 단일 단지 PDF(예: 2021년 행복주택(상아2차)) → 제목의 괄호 안 이름으로 채움
            one = re.search(r'행복주택\s*\(([^)]+)\)', x['title'])
            for r in rows:
                if not r.get('danji') and one: r['danji'] = one.group(1)
            # 사이트용으로 슬림화: 빈 값·화면에 안 쓰는 열(인터넷/방문/공가/예비 세부) 제거
            DROP = ('net', 'visit', 'total', 'vac', 'wait')
            rows = [{k: v for k, v in r.items() if v not in (None, '') and k not in DROP} for r in rows]
            bt = body_total(text) if text else (old.get(seq) or {}).get('body_total')
            sum_n = sum((r.get('n') or 0) for r in rows); sum_s = sum((r.get('sum') or 0) for r in rows)
            calc = {'supply': sum_n, 'sum': sum_s, 'rate': round(sum_s / sum_n, 1) if sum_n else None}
            posts[seq] = {'seq': seq, 'title': x['title'], 'date': x['date'], 'kind': x['kind'], 'label': label_of(x['title'], x['kind']),
                          'url': SH_VIEW.format(seq=seq), 'files': parsed_files, 'total': total, 'body_total': bt, 'calc': calc, 'rows': rows, 'pv': rates.PARSER_VER,
                          'parsed_at': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y-%m-%d %H:%M')}
            ok = (bt or total or {}).get('rate')
            log(f"{seq} {x['date']} {x['kind']} rows={len(rows)} calc={calc['rate']} official={ok} {'OK' if ok and calc['rate'] and abs(calc['rate'] - ok) < 0.6 else 'CHECK'} :: {x['title'][:60]}")
        except Exception as e:
            log('post fail', seq, repr(e))
    out = {'updated': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y-%m-%d %H:%M KST'),
           'source': 'SH 인터넷청약 공고 게시판(최종 청약 경쟁률 게시 / 선순위 청약접수결과) 첨부 PDF', 'posts': posts}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    log('wrote', OUT, 'posts', len(posts), 'rows', sum(len(p.get('rows') or []) for p in posts.values()))

if __name__ == '__main__':
    main(reparse='--all' in sys.argv, offline='--offline' in sys.argv)
