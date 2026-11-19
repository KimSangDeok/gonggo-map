#!/usr/bin/env python3
"""Claude 확인용 로그 한 번에 보기(2026-11-19 사용자 '니가 확인 할만한 로그는 전부 추가해').

  python3 tools/read_logs.py            기기 기록(prefs 가지 log/*.json) — 기기마다 머리줄 + 최근 25건
  python3 tools/read_logs.py -n 60      최근 60건
  python3 tools/read_logs.py --hours 24 최근 24시간 것만
  python3 tools/read_logs.py --actions  GitHub Actions: 워크플로마다 마지막 실행 + 최근 3일 실패 목록
  python3 tools/read_logs.py --push     알림 보낸 기록(data/alerts.json 의 pushed·err·push_res) 최근 10건
  python3 tools/read_logs.py --data     자료 파일별 마지막 갱신 커밋(수집이 멈췄는지)
  python3 tools/read_logs.py --all      위 넷 다

기기 기록은 사이트(index.html 의 errLog)가 기기 동기화 토큰으로 올린 것 — 기술 정보만(금액·토큰·바깥 주소 경로는 지움).
gh(로그인된 GitHub CLI)가 있어야 함. 토큰 값은 이 스크립트가 다루지 않음.
"""
import argparse, base64, datetime, json, subprocess, sys

REPO = 'KimSangDeok/gonggo-map'
KST = datetime.timezone(datetime.timedelta(hours=9))
K = {'js': '스크립트 오류', 'promise': '스크립트 오류(비동기)', 'console': '콘솔 오류', 'reload': '페이지 다시 열림', 'crash': '갑자기 다시 열림',
     'bg': '백그라운드 정리 뒤 다시 열림', 'lb-img': '크게 보기 그림', 'res': '파일 못 불러옴', 'net': '자료 요청 실패', 'slow': '느림', 'map': '지도',
     'sync': '기기 동기화', 'push': '알림 구독', 'sw': '알림(서비스 워커)', 'upd': '사이트 판'}


def gh_json(*args):
    r = subprocess.run(['gh', *args], capture_output=True, text=True)
    if r.returncode:
        return None
    try:
        return json.loads(r.stdout)
    except Exception:
        return None


def when(s):
    try:
        return datetime.datetime.fromisoformat(str(s).replace('Z', '+00:00')).astimezone(KST)
    except Exception:
        return None


def hm(s):
    t = when(s)
    return t.strftime('%m-%d %H:%M:%S') if t else str(s)


def device_logs(n, hours):
    ls = gh_json('api', f'repos/{REPO}/contents/log?ref=prefs')
    if not isinstance(ls, list) or not ls:
        print('기기 기록 없음 — prefs 가지에 log/ 가 아직 없음(기기 동기화가 켜진 기기가 새 판을 열면 20초 뒤 올라옴)')
        return
    cut = datetime.datetime.now(KST) - datetime.timedelta(hours=hours) if hours else None
    for f in sorted(ls, key=lambda x: x.get('name', '')):
        j = gh_json('api', f'repos/{REPO}/contents/log/{f["name"]}?ref=prefs')
        if not j or not j.get('content'):
            print('==', f.get('name'), '읽기 실패')
            continue
        try:
            doc = json.loads(base64.b64decode(j['content']).decode('utf-8'))
        except Exception as e:
            print('==', f.get('name'), '해석 실패', repr(e)[:80])
            continue
        dv = doc.get('dev') or {}
        pf = dv.get('perf') or {}
        print(f"== {dv.get('name')} [{dv.get('id')}] 올림 {hm(doc.get('up'))} · 판 {dv.get('build')} · 알림 권한 {dv.get('notif')} · 구독 {dv.get('push')} · SW {dv.get('sw')}"
              f" · 화면 {dv.get('scr')} 창 {dv.get('win')} · 첫 화면 {pf.get('load')}ms({pf.get('type')}, {pf.get('kb')}KB) · 저장 {dv.get('store')} · 메모리 {dv.get('mem')}GB")
        print('   UA', dv.get('ua'))
        logs = doc.get('logs') or []
        if cut:
            logs = [x for x in logs if (when(x.get('t2') or x.get('t')) or cut) >= cut]
        print(f'   기록 {len(doc.get("logs") or [])}건' + (f' · 최근 {hours}시간 {len(logs)}건' if cut else '') + f' · 아래 최근 {min(n, len(logs))}건')
        for x in logs[-n:]:
            cnt = f" ×{x['n']}" if (x.get('n') or 1) > 1 else ''
            t2 = f"~{hm(x['t2'])[6:]}" if x.get('t2') else ''
            print(f"  {hm(x.get('t'))}{t2} [{K.get(x.get('k'), x.get('k'))}{cnt}] {x.get('m', '')}" + (f" | {x['x']}" if x.get('x') else '') + (f" (판 {x.get('b')}, 창 {x.get('w')}{', 오프라인' if x.get('off') else ''}{', JS ' + x['mem'] if x.get('mem') else ''})"))
            if x.get('c'):
                print('      직전 동작:', x['c'])


def actions(days=3):
    runs = gh_json('run', 'list', '-R', REPO, '-L', '200', '--json', 'workflowName,conclusion,status,createdAt,databaseId,event,headBranch')
    if not isinstance(runs, list):
        print('Actions 목록을 못 읽음')
        return
    last = {}
    for r in runs:
        last.setdefault(r['workflowName'], r)
    print('== Actions 워크플로별 마지막 실행')
    for w, r in sorted(last.items()):
        print(f"  {w}: {r.get('conclusion') or r.get('status')} · {hm(r.get('createdAt'))} · {r.get('event')} · id {r.get('databaseId')}")
    cut = datetime.datetime.now(KST) - datetime.timedelta(days=days)
    bad = [r for r in runs if r.get('conclusion') not in ('success', 'skipped', None, '') and (when(r.get('createdAt')) or cut) >= cut]
    print(f'== 최근 {days}일 실패·취소 {len(bad)}건' + (' — 자세히: gh run view <id> --log-failed' if bad else ''))
    for r in bad[:30]:
        print(f"  {hm(r.get('createdAt'))} {r['workflowName']}: {r.get('conclusion')} · id {r.get('databaseId')}")


def push_log(k=10):
    j = gh_json('api', f'repos/{REPO}/contents/data/alerts.json?ref=gh-pages')
    if not j:
        print('alerts.json 못 읽음')
        return
    try:
        if j.get('content'):
            st = json.loads(base64.b64decode(j['content']).decode('utf-8'))
        else:   # 1MB 넘으면 contents API 가 내용을 안 줌 → blob 으로
            b = gh_json('api', f"repos/{REPO}/git/blobs/{j['sha']}")
            st = json.loads(base64.b64decode(b['content']).decode('utf-8'))
    except Exception as e:
        print('alerts.json 해석 실패', repr(e)[:80])
        return
    print(f"== 알림 기록(data/alerts.json) 갱신 {st.get('updated')} — 최근 {k}건")
    for x in (st.get('log') or [])[-k:]:
        print('  ' + ' · '.join(f'{a}={x[a]}' for a in ('at', 'key', 'send', 'pushed', 'err', 'push_res', 'dead_subs', 'claude') if x.get(a) not in (None, '')))


DATA = ['data/notices.json', 'data/ya.json', 'data/lh.json', 'data/alerts.json', 'data/thumbs.json', 'data/plans.json', 'data/rates.json', 'data/pamphlets.json', 'data/fact.json', 'version.json']


def data_fresh():
    print('== 자료 파일 마지막 갱신(gh-pages 커밋)')
    for f in DATA:
        c = gh_json('api', f'repos/{REPO}/commits?sha=gh-pages&path={f}&per_page=1')
        if not c:
            print(f'  {f}: 기록 없음')
            continue
        c = c[0]
        t = when(c['commit']['committer']['date'])
        age = (datetime.datetime.now(KST) - t).total_seconds() / 3600 if t else 0
        print(f"  {f}: {hm(c['commit']['committer']['date'])} ({age:.0f}시간 전) · {c['commit']['message'].splitlines()[0][:70]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-n', type=int, default=25)
    ap.add_argument('--hours', type=float, default=0)
    ap.add_argument('--actions', action='store_true')
    ap.add_argument('--push', action='store_true')
    ap.add_argument('--data', action='store_true')
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--no-device', action='store_true')
    a = ap.parse_args()
    if not a.no_device:
        device_logs(a.n, a.hours)
    if a.actions or a.all:
        actions()
    if a.push or a.all:
        push_log()
    if a.data or a.all:
        data_fresh()


if __name__ == '__main__':
    sys.exit(main())
