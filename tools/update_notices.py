# -*- coding: utf-8 -*-
"""매일 실행: SH 공고 게시판 + LH 청약플러스(서울) + 서울시 청년안심주택(공고 게시판·단지)을 읽어 data/notices.json, data/lh.json, data/ya.json 생성."""
import json, datetime, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sources as src
KNOWN = {'304864': 'H26-1', '309337': 'H26-2', '308340': 'K26', '292541': 'K25'}   # 지도에 단지표가 반영된 공고
os.makedirs('data', exist_ok=True)
now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y-%m-%d %H:%M KST')
out = {'updated': now, 'source': src.SH_LIST, 'known': KNOWN, 'items': []}
try:
    out['items'] = src.sh_notices(set(KNOWN))
except Exception as e:
    src.log('SH failed:', repr(e))
lh = {'updated': now, 'source': src.LH_LIST, 'items': []}
try:
    lh['items'] = src.lh_notices()
except Exception as e:
    src.log('LH failed:', repr(e))
# 서울시 청년안심주택: 공고(공공·민간) + 단지(좌표·규모·입주현황). 단지 상세는 99곳×1회라 매일 돌려도 가벼움
ya = {'updated': now, 'source': src.YA + '/bbs/BMSR00015/list.do?menuNo=400008', 'list_url': src.YA + '/pgm/home/yohome/list.do?menuNo=400002', 'notices': [], 'complexes': []}
try:
    ya['notices'] = src.ya_notices()
except Exception as e:
    src.log('YA notices failed:', repr(e))
try:
    ya['complexes'] = src.ya_complexes()
except Exception as e:
    src.log('YA complexes failed:', repr(e))
if not ya['complexes'] and os.path.exists('data/ya.json'):   # 실패한 날은 기존 단지 데이터 유지
    try: ya['complexes'] = json.load(open('data/ya.json', encoding='utf-8')).get('complexes', [])
    except Exception: pass
out['log'] = src.LOG[-60:]
json.dump(out, open('data/notices.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
json.dump(lh, open('data/lh.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
json.dump(ya, open('data/ya.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print('notices', len(out['items']), 'lh', len(lh['items']), 'ya notices', len(ya['notices']), 'ya complexes', len(ya['complexes']))
