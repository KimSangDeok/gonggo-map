# -*- coding: utf-8 -*-
"""매일 실행: SH 공고 게시판 + LH 청약플러스(서울) + 서울시 청년안심주택(공고 게시판·단지)을 읽어 data/notices.json, data/lh.json, data/ya.json 생성."""
import json, datetime, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sources as src
KNOWN = {'304864': 'H26-1', '309337': 'H26-2', '308340': 'K26', '292541': 'K25'}   # 지도에 단지표가 반영된 공고
os.makedirs('data', exist_ok=True)
def _load(f):
    try: return json.load(open(f, encoding='utf-8'))
    except Exception: return {}
PREV_N, PREV_L, PREV_Y = _load('data/notices.json'), _load('data/lh.json'), _load('data/ya.json')   # 한 곳이 실패하면 그곳은 지난 자료 유지(빈 목록으로 덮지 않음)
OK = {}
now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y-%m-%d %H:%M KST')
out = {'updated': now, 'source': src.SH_LIST, 'known': KNOWN, 'items': []}
try:
    out['items'] = src.sh_notices(set(KNOWN)); OK['sh'] = True
except Exception as e:
    src.log('SH failed:', repr(e)); out['items'] = PREV_N.get('items', [])
lh = {'updated': now, 'source': src.LH_LIST, 'items': []}
try:
    lh['items'] = src.lh_notices(); OK['lh'] = True
except Exception as e:
    src.log('LH failed:', repr(e)); lh['items'] = PREV_L.get('items', [])
# 서울시 청년안심주택: 공고(공공·민간) + 단지(좌표·규모·입주현황). 단지 상세는 99곳×1회라 매일 돌려도 가벼움
ya = {'updated': now, 'source': src.YA + '/bbs/BMSR00015/list.do?menuNo=400008', 'list_url': src.YA + '/pgm/home/yohome/list.do?menuNo=400002', 'notices': [], 'complexes': []}
try:
    ya['notices'] = src.ya_notices(); OK['ya'] = True
except Exception as e:
    src.log('YA notices failed:', repr(e)); ya['notices'] = PREV_Y.get('notices', [])
try:
    ya['complexes'] = src.ya_complexes()
except Exception as e:
    src.log('YA complexes failed:', repr(e))
if not ya['complexes'] and os.path.exists('data/ya.json'):   # 실패한 날은 기존 단지 데이터 유지
    try: ya['complexes'] = json.load(open('data/ya.json', encoding='utf-8')).get('complexes', [])
    except Exception: pass
# 기관 공급계획(공고 예고): SH 청약 공급계획(행복주택·국민임대·청년안심주택) + LH 공급계획(임대, 서울) — 실패한 날은 기존 것 유지
plans = {'updated': now, 'about': '기관이 미리 밝힌 공급계획(아직 공고 전) — SH 인터넷청약 청약 공급계획 · LH 청약플러스 공급계획(임대주택, 서울). 이미 공고가 났는지·계획 시기가 지났는지는 지도 화면에서 판정', 'items': []}
try:
    plans['items'] = src.sh_plans() + src.lh_plans()
except Exception as e:
    src.log('plans failed:', repr(e))
if not plans['items'] and os.path.exists('data/plans.json'):
    try: plans['items'] = json.load(open('data/plans.json', encoding='utf-8')).get('items', [])
    except Exception: pass
json.dump(plans, open('data/plans.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
# 목록에서 본 글 번호 — check_new.py 가 5분마다 이것과 비교해 새 글이면 이 수집을 바로 돌림. 실패했거나 0건인 곳은 지난 값 유지
PL = PREV_N.get('list_ids') or {}
out['list_ids'] = {k: (src.SEEN[k] if OK.get(k) and src.SEEN[k] else (PL.get(k) or [])) for k in ('sh', 'lh', 'ya')}
# 처음 본 시각(KST) — 5분마다 확인 + 새 글이면 바로 이 수집이라 '게시 후 몇 분 안'의 시각. 공고가 보통 몇 시에 올라오는지 재는 근거(SH·LH 페이지엔 날짜만 있음)
# 이 기록을 시작한 때 이미 있던 글은 시각을 모르므로 null
FS = PREV_N.get('first_seen')
stamp = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y-%m-%d %H:%M')
if FS is None: FS = {k + ':' + x: None for k in ('sh', 'lh', 'ya') for x in out['list_ids'][k]}
else:
    for k in ('sh', 'lh', 'ya'):
        for x in out['list_ids'][k]:
            FS.setdefault(k + ':' + x, stamp)
keep = {k + ':' + x for k in ('sh', 'lh', 'ya') for x in out['list_ids'][k]}
out['first_seen'] = {k: v for k, v in FS.items() if k in keep or v}   # 목록에서 빠져도 시각이 있는 건 남김(통계용)
out['log'] = src.LOG[-60:]
json.dump(out, open('data/notices.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
json.dump(lh, open('data/lh.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
json.dump(ya, open('data/ya.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print('plans', len(plans['items']), 'notices', len(out['items']), 'lh', len(lh['items']), 'ya notices', len(ya['notices']), 'ya complexes', len(ya['complexes']))
