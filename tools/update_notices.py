# -*- coding: utf-8 -*-
"""매일 실행: SH 공고 게시판 + LH 청약플러스(경기·서울)를 읽어 data/notices.json, data/lh.json 생성."""
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
out['log'] = src.LOG[-40:]
json.dump(out, open('data/notices.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
json.dump(lh, open('data/lh.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('notices', len(out['items']), 'lh', len(lh['items']))
