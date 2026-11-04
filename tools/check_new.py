# -*- coding: utf-8 -*-
"""새 공고 빨리 잡기(.github/workflows/check-new.yml, 5분마다).
SH 공고 게시판 1쪽 · LH 청약플러스 서울 목록 · 서울시 청년안심 게시판 1쪽만 읽고(요청 3번, 상세·첨부·PDF는 안 읽음)
지난 전체 수집(update_notices.py)이 목록에서 본 글 번호(data/notices.json 'list_ids')에 없는 글이 있으면 new=1 을 남김
→ 워크플로가 전체 수집(update-notices: 상세·경쟁률·알림)을 바로 돌림. 기관 사이트 부담은 사람이 5분마다 목록을 한 번 여는 정도."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sources as src

def load(f):
    try: return json.load(open(f, encoding='utf-8'))
    except Exception: return {}

base = load('data/notices.json').get('list_ids')
new, fail = [], []
for k, fn in (('sh', lambda: src.sh_list(pages=1)), ('lh', src.lh_rows), ('ya', lambda: src.ya_notices(pages=1))):
    try:
        fn()
    except Exception as e:
        fail.append(k); src.log(k, '목록 못 읽음:', repr(e)); continue
    if base is None:                       # 이 기능을 넣은 뒤 아직 전체 수집이 기준을 안 남김 → 한 번 돌려 기준을 만듦
        if src.SEEN[k]: new.append(k + ':기준 없음')
        continue
    have = set(map(str, base.get(k) or []))
    if not have: continue                  # 그곳 기준이 비어 있으면(지난 수집 실패) 비교하지 않음 — 다음 정기 수집이 채움
    new += [k + ':' + x for x in src.SEEN[k] if x not in have]
msg = '새 글 ' + (', '.join(new) if new else '없음') + ' · 본 글 SH ' + str(len(src.SEEN['sh'])) + ' · LH ' + str(len(src.SEEN['lh'])) + ' · 청년안심 ' + str(len(src.SEEN['ya'])) + (' · 못 읽음 ' + ','.join(fail) if fail else '')
print(msg)
print('::notice title=check-new::' + msg)   # 실행 기록에 주석으로 남김
out = os.environ.get('GITHUB_OUTPUT')
if out:
    with open(out, 'a', encoding='utf-8') as f: f.write('new=' + ('1' if new else '0') + '\n')
