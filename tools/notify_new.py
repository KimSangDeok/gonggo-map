# -*- coding: utf-8 -*-
"""새 공고 알림 — update_notices.py 직후 실행.
data/notices.json(SH 게시판)·lh.json(LH 청약플러스 서울)·ya.json(서울시 청년안심 게시판)에서 처음 보는 모집공고만 골라
① 웹 푸시(사이트에서 구독한 기기 data/push/*.json, 서명 키는 저장소 비밀값 PUSH_SEED 에서 유도) ② ntfy(NTFY_TOPIC — 비밀값, 있으면)
③ data/alerts.json 기록(Claude 앱 예약 작업이 읽음). 비밀값이 없으면 기록만 함.

보내는 것
- SH: 모집공고(제목에 모집·공급 공고) 중 행복주택·국민임대·통합공공임대·청년안심·매입임대·전세임대. 장기전세·재개발·영구임대 빼고,
      신혼·고령자 등 청년이 아닌 계층만 대상인 공고도 뺌(제목 기준)
- LH 서울: 새 공고 전부(정정공고·영구임대·청년 아닌 계층 전용 제외)
- 청년안심(민간): 지도와 같은 규칙(build_site.py yaSplit·fitArea·yaNoticesFor)으로 청년 자격 형이 전용 8평(26.45㎡) 이상이거나
      26㎡대(경계)인 단지, 또는 단지 매칭이 안 돼 판정 못 한 공고. 원룸(8평 미만)뿐이면 기록만 하고 안 보냄.
      청년안심 공공임대 공고는 SH 게시판에도 올라오므로 SH 쪽으로 보냄(중복 방지)
첫 실행(alerts.json 없음)은 지금 있는 공고를 '본 것'으로만 기록하고 보내지 않음.
사용: python tools/notify_new.py [--dry-run] [--test]"""
import json, os, re, sys, glob, base64, datetime, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def D(f): return os.path.join(ROOT, 'data', f)
STATE = D('alerts.json')
KST = datetime.timezone(datetime.timedelta(hours=9))
NOW = datetime.datetime.now(KST)
SITE = 'https://kimsangdeok.github.io/gonggo-map/'
DRY = '--dry-run' in sys.argv
TOPIC = os.environ.get('NTFY_TOPIC', '').strip()

def load(f, default):
    try: return json.load(open(f, encoding='utf-8'))
    except Exception: return default

# ---------- 청년안심 판정: build_site.py 의 JS 와 같은 규칙(기준 = 8평 이상) ----------
def m2ofPy(v): return round(v * 3.3058 * 100) / 100           # 8평 26.45 · 9평 29.75 · 10평 33.06㎡
FLOOR = m2ofPy(8)
BOUNDS = [m2ofPy(k) for k in (8, 9, 10)]
def in_sel(v): return v >= FLOOR
def bnd_in(a, b): return any(a < m < b for m in BOUNDS)
def fit_range(a, b):                                           # 1 전부 기준 이상 · 0 전부 미만 · 2 경계가 그 ㎡대 안을 지남
    s1, s2 = in_sel(a), in_sel(b - 0.001)
    if not bnd_in(a, b): return 1 if s1 else 0
    return 1 if (s1 and s2) else (0 if (not s1 and not s2) else 2)
def ty_exact(ty):
    m = re.search(r'(\d{2,3}\.\d{1,2})', str(ty or '')); return float(m.group(1)) if m else None
def ty_num(ty):
    m = re.search(r'(\d{2})', str(ty or '')); return int(m.group(1)) if m else None
def fit_area(ty):
    e = ty_exact(ty)
    if e: return 1 if in_sel(e) else 0
    n = ty_num(ty)
    if not n: return None
    return fit_range(n, n + 1)
DUP = re.compile(r'복층|2층형|이층형|메자닌|듀플렉스|다락', re.I)
SHARE = re.compile(r'셰어|쉐어|공유')
def ya_split(c):
    ok, anyrow = [], False
    for g in ('special', 'general'):
        for r in ((c.get('rows') or {}).get(g) or []):
            anyrow = True
            if '청년' not in (r.get('who') or ''): continue
            t = (r.get('room') or '') + ' ' + (r.get('ty') or '')
            if DUP.search(t) or SHARE.search(t): continue
            f = fit_area(r.get('ty'))
            if f in (1, 2): ok.append((r, f))
    return ok, anyrow
def ya_key(name): return re.sub(r'청년안심주택|청년주택', '', re.sub(r'\s+', '', name or ''))
def ya_fit(n, comps):
    """('8평 이상' | '경계' | '원룸뿐' | '판정 불가', 설명)"""
    t = re.sub(r'\s+', '', n.get('title') or '')
    cs = []
    for c in comps:
        key = ya_key(c.get('name')); k6 = key[:6]
        if k6 and (k6 in t or (len(key) >= 4 and key in t)): cs.append(c)
    okc, nac = [], 0
    for c in cs:
        ok, anyrow = ya_split(c)
        if ok: okc.append((c, ok))
        elif anyrow: nac += 1
    if okc:
        def area(r): return ty_exact(r.get('ty')) or ty_num(r.get('ty'))
        def py(v): return f'{float(v) / 3.3058:.1f}'                    # ㎡ → 평(1평 = 3.3058㎡)
        def span(xs, f): return (f(xs[0]) + ('~' + f(xs[-1]) if len(xs) > 1 else '')) if xs else ''
        full = sorted({area(r) for _, ok in okc for r, f in ok if f == 1} - {None})    # 전부 8평 이상인 형
        bord = sorted({area(r) for _, ok in okc for r, f in ok if f == 2} - {None})    # ㎡대 안을 8평 경계가 지나는 형
        border = all(f == 2 for _, ok in okc for _, f in ok)
        names = '·'.join(c.get('name', '') for c, _ in okc)
        parts = []
        if full: parts.append(f'청년형 전용 {span(full, str)}㎡({span(full, py)}평)')
        if bord: parts.append(f'경계 {span(bord, str)}㎡대(약 {span(bord, py)}평 — 8평 = 26.45㎡ 경계가 이 ㎡대 안을 지나 공고문 평면도로 확인)')
        if not parts: parts.append('청년형 면적 표기 없음 → 공고문 확인')
        return ('경계' if border else '8평 이상'), names + ' · ' + ' · '.join(parts)
    if cs and nac == len(cs): return '원룸뿐', '청년 자격 형이 전부 8평 미만'
    if cs: return '판정 불가', '서울시 단지정보에 형별 표가 없음 → 공고문 확인'
    return '판정 불가', '제목으로 단지 매칭 안 됨 → 공고문 확인'

# ---------- 대상 고르기 ----------
SH_CATS = {'행복주택', '국민임대', '통합공공임대', '청년안심', '매입임대', '전세임대'}
NOT_YOUTH = re.compile(r'신혼|신생아|다자녀|고령자|어르신|주거취약|노숙|쪽방|장애인|대학생|기숙사|희망하우징|영구임대')
def youth_ok(title): return not (NOT_YOUTH.search(title or '') and '청년' not in (title or ''))
def step(it, name):
    for s in it.get('steps') or []:
        if s and s[0] == name: return s[1] + ('~' + s[2] if len(s) > 2 and s[2] else '')
    return ''

def collect():
    out = []
    for it in (load(D('notices.json'), {}).get('items') or []):
        if not it.get('seq') or it.get('kind') != '공고' or it.get('cat') not in SH_CATS: continue
        title = it.get('title') or ''
        if not title or not youth_ok(title): continue
        ap = step(it, '접수')
        out.append({'key': 'sh:' + str(it['seq']), 'src': 'SH ' + it.get('cat', ''), 'title': title, 'url': it.get('url'),
                    'posted': it.get('date') or step(it, '공고'), 'apply': ap, 'fit': '', 'why': '', 'send': not re.search(r'정정', title), 'prio': 4})
    for it in (load(D('lh.json'), {}).get('items') or []):
        title = it.get('title') or ''
        if not it.get('panId'): continue
        send = not re.search(r'정정', title) and youth_ok(title) and (it.get('type') or '') != '영구임대'
        out.append({'key': 'lh:' + str(it['panId']), 'src': 'LH 서울 ' + (it.get('type') or ''), 'title': title, 'url': it.get('url') or 'https://apply.lh.or.kr/lhapply/apply/wt/wrtanc/selectWrtancList.do?mi=1026',
                    'posted': it.get('posted') or '', 'apply': ('~' + it['deadline']) if it.get('deadline') else '', 'fit': '', 'why': '', 'send': send, 'prio': 4})
    ya = load(D('ya.json'), {})
    comps = ya.get('complexes') or []
    for n in ya.get('notices') or []:
        if not n.get('id'): continue
        if n.get('kind') == '공공임대':
            fit, why, send = '', 'SH 게시판 공고로 따로 알림', False
        else:
            fit, why = ya_fit(n, comps); send = fit != '원룸뿐'
        out.append({'key': 'ya:' + str(n['id']), 'src': '청년안심 ' + (n.get('kind') or ''), 'title': n.get('title') or '', 'url': n.get('url'),
                    'posted': n.get('posted') or '', 'apply': n.get('apply') or '', 'fit': fit, 'why': why, 'send': send, 'prio': 3})
    return out

def ntfy(title, msg, url, prio=3, tags=('house',)):
    body = {'topic': TOPIC, 'title': title[:120], 'message': msg[:1000], 'priority': prio, 'tags': list(tags),   # ntfy 메시지 한도 4,096바이트(한글 3바이트) 안으로
            'actions': [{'action': 'view', 'label': '공고 열기', 'url': url}, {'action': 'view', 'label': '내 지도', 'url': SITE}]}
    if url: body['click'] = url
    req = urllib.request.Request('https://ntfy.sh/', data=json.dumps(body, ensure_ascii=False).encode('utf-8'), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=25) as r: r.read()

# ---------- 웹 푸시(직접 발송): 사이트 '이 기기로 알림 받기'로 만든 구독(data/push/*.json)에 VAPID 서명으로 보냄 ----------
# 브라우저 회사 푸시 서버(구글 FCM·애플·모질라)로 바로 감. 본문은 RFC 8291 로 암호화돼 그 서버도 못 읽음
# 서명 키: 저장소 비밀값 PUSH_SEED(사용자가 정한 긴 무작위 문자열)에서 매번 같은 키를 유도 — 개인키를 사람이 옮길 일이 없음.
# PBKDF2(60만 회)라 공개키로부터 씨앗을 거꾸로 맞히기도 느림. 공개키는 data/push/vapid_public.txt 에 써서 사이트 구독 버튼이 읽음
PUSH_SEED = os.environ.get('PUSH_SEED', '').strip()
PUB_FILE = D(os.path.join('push', 'vapid_public.txt'))
def _b64u(b): return base64.urlsafe_b64encode(b).rstrip(b'=').decode()
def vapid_from_seed(seed):
    import hashlib
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization
    n = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551   # P-256 차수
    okm = hashlib.pbkdf2_hmac('sha256', seed.encode('utf-8'), b'gonggo-map/vapid/v1', 600000, dklen=48)
    d = int.from_bytes(okm, 'big') % (n - 1) + 1
    pub = ec.derive_private_key(d, ec.SECP256R1()).public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return _b64u(d.to_bytes(32, 'big')), _b64u(pub)
VAPID_PRIVATE, VAPID_PUBLIC = vapid_from_seed(PUSH_SEED) if PUSH_SEED else ('', '')
def write_public():
    if not VAPID_PUBLIC: return False
    cur = open(PUB_FILE, encoding='utf-8').read().strip() if os.path.exists(PUB_FILE) else ''
    if cur == VAPID_PUBLIC: return False
    os.makedirs(os.path.dirname(PUB_FILE), exist_ok=True); open(PUB_FILE, 'w', encoding='utf-8').write(VAPID_PUBLIC + '\n'); return True
DEAD = []
def push_subs():
    out = []
    for f in sorted(glob.glob(D(os.path.join('push', '*.json')))):
        sub = load(f, None)
        if sub and sub.get('endpoint') and (sub.get('keys') or {}).get('p256dh') and (sub.get('keys') or {}).get('auth'): out.append((f, sub))
    return out
def webpush_all(title, msg, url, urgent=False, key=''):
    if not VAPID_PRIVATE: return 0
    from pywebpush import webpush, WebPushException
    n = 0
    for f, sub in push_subs():
        if f in DEAD: continue
        try:
            webpush(subscription_info={'endpoint': sub['endpoint'], 'keys': sub['keys']},
                    data=json.dumps({'title': title[:120], 'body': msg[:1000], 'url': url or SITE, 'key': key}, ensure_ascii=False),   # key: 알림 누르면 사이트 목록에서 확인 처리
                    vapid_private_key=VAPID_PRIVATE, vapid_claims={'sub': 'https://kimsangdeok.github.io'}, ttl=3 * 86400, headers={'Urgency': 'high' if urgent else 'normal'})
            n += 1
        except WebPushException as e:
            code = getattr(getattr(e, 'response', None), 'status_code', None)
            if code in (404, 410): DEAD.append(f)          # 구독 만료(앱 지움·브라우저 데이터 삭제 등) → 파일 지우고 기록
            else: raise
    return n

def notify(title, msg, url, prio=3, key=''):
    """두 경로로 보냄. 돌려주는 값: 보낸 경로 목록"""
    done, errs = [], []
    if TOPIC:
        try: ntfy(title, msg, url, prio); done.append('ntfy')
        except Exception as e: errs.append('ntfy ' + repr(e)[:120])
    if VAPID_PRIVATE:
        try:
            k = webpush_all(title, msg, url, prio >= 4, key)
            if k: done.append('webpush×' + str(k))
        except Exception as e: errs.append('webpush ' + repr(e)[:120])
    return done, errs

def main():
    if '--test' in sys.argv:
        if not (TOPIC or VAPID_PRIVATE): print('NTFY_TOPIC·PUSH_SEED 둘 다 없음'); return
        cur = open(PUB_FILE, encoding='utf-8').read().strip() if os.path.exists(PUB_FILE) else ''
        if VAPID_PUBLIC and cur != VAPID_PUBLIC: print('주의: data/push/vapid_public.txt 가 지금 비밀값의 공개키와 다름 → update-notices 한 번 돌려 갱신하고 다시 구독해야 함')
        done, errs = notify('공공임대 공고 알림 테스트', '이 알림이 보이면 연결 끝. 새 모집공고가 잡히면(매일 09:23·15:23 수집) 이렇게 옵니다.', SITE + '#calendar', 3)
        print('test', done, errs, 'subs', len(push_subs()), 'dead', [os.path.basename(f) for f in DEAD]); return
    if not DRY and write_public(): print('vapid public key written')
    st = load(STATE, None)
    items = collect()
    today = NOW.strftime('%Y-%m-%d')
    if st is None:   # 첫 실행: 지금 있는 것은 본 것으로만
        st = {'seen': {it['key']: today for it in items}, 'log': [{'at': NOW.strftime('%Y-%m-%d %H:%M KST'), 'init': len(items)}]}
        new = []
    else:
        seen = st.setdefault('seen', {})
        new = [it for it in items if it['key'] not in seen]
        for it in new: seen[it['key']] = today
    sent = 0
    for it in new:
        it['at'] = NOW.strftime('%Y-%m-%d %H:%M KST')
        if it['send'] and (TOPIC or VAPID_PRIVATE) and not DRY and sent < 8:
            msg = it['src'] + ' · 게시 ' + (it['posted'] or '?') + (' · 접수 ' + it['apply'] if it['apply'] else '')
            if it['fit']: msg += '\n' + ('내 조건(청년·8평↑): ' + it['fit']) + (' — ' + it['why'] if it['why'] else '')
            done, errs = notify(it['title'] or it['src'], msg, it['url'], it['prio'], it['key'])
            it['pushed'] = ', '.join(done) if done else False
            if errs: it['err'] = ' / '.join(errs)[:240]
            if done: sent += 1
        st['log'].append({k: it.get(k) for k in ('at', 'key', 'src', 'title', 'url', 'posted', 'apply', 'fit', 'why', 'send', 'pushed', 'err') if it.get(k) not in (None, '')})
    if len([it for it in new if it['send']]) > 8 and (TOPIC or VAPID_PRIVATE) and not DRY:
        try: notify('새 공고가 더 있음', '한 번에 ' + str(len(new)) + '건이 새로 잡혀 8건만 따로 보냈습니다. 나머지는 사이트 공고 일정 탭에서 확인.', SITE + '#calendar', 3)
        except Exception: pass
    if DEAD and not DRY:
        for f in DEAD:
            try: os.remove(f)
            except Exception: pass
        st['log'].append({'at': NOW.strftime('%Y-%m-%d %H:%M KST'), 'dead_subs': [os.path.basename(f) for f in DEAD], 'why': '푸시 서버가 404/410(구독 만료) — 사이트에서 다시 구독·등록 필요'})
    # 정리: 지금 목록에 없고 400일 지난 키는 지움, 기록은 최근 300건만
    keys = {it['key'] for it in items}; cut = (NOW - datetime.timedelta(days=400)).strftime('%Y-%m-%d')
    st['seen'] = {k: v for k, v in st['seen'].items() if k in keys or v >= cut}
    st['log'] = st['log'][-300:]
    st['updated'] = NOW.strftime('%Y-%m-%d %H:%M KST')
    st['about'] = '새 모집공고 알림 기록(tools/notify_new.py). send=알림 대상 여부, pushed=보낸 경로(ntfy·webpush×기기 수). 청년안심은 fit(8평 이상·경계·원룸뿐·판정 불가)으로 거름'
    if not DRY: json.dump(st, open(STATE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('items', len(items), 'new', len(new), 'to-send', sum(1 for it in new if it['send']), 'pushed', sent, 'subs', len(push_subs()), '(dry-run)' if DRY else '')
    for it in new: print(' ', 'SEND' if it['send'] else 'skip', it['key'], it['src'], '|', it['title'][:60], '|', it['fit'], it['why'][:60])

if __name__ == '__main__':
    main()
