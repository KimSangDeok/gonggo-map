# -*- coding: utf-8 -*-
"""매월 실행: SH 주택정보 + K-apt에서 단지 수치(공가·1년 퇴거·관리비·주차 등)를 다시 받아 data/fact.json 생성."""
import json, re, datetime, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sources as src, facts
html = open('index.html', encoding='utf-8').read()
PLACES = json.loads(re.search(r"var PLACES = (\[.*?\]);\n", html, re.S).group(1))
cds = sorted({cd for cds, _ in facts.MAP.values() for cd in cds})
src.hi_init(); SH = {}
for cd in cds:
    try: SH[cd] = src.hi_fetch(cd)
    except Exception as e: src.log('SH houseinfo fail', cd, repr(e))
    time.sleep(0.3)
src.log('SH houseinfo:', len(SH), 'of', len(cds))
facts.SH.update(SH)
codes = set()
for cds_, kapts in facts.MAP.values():
    if kapts is not None: codes.update(kapts)
    else:
        for cd in cds_:
            k = SH.get(cd, {}).get('kapt')
            if k and k not in facts.BAD_KAPT: codes.add(k)
K = {}
try:
    src.kapt_init()
    for c in sorted(codes):
        try: K[c] = src.kapt_fetch(c)
        except Exception as e: src.log('K-apt fail', c, repr(e))
        time.sleep(0.3)
except Exception as e:
    src.log('K-apt init fail', repr(e))
src.log('K-apt:', len(K), 'of', len(codes))
facts.load(SH, K)
now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y-%m-%d %H:%M KST')
F = {(p['name'] + '|' + str(p.get('m2', ''))): facts.facts_for(p['name'], p.get('m2'), p['kind']) for p in PLACES}
ok = sum(1 for v in F.values() if v.get('k') or v.get('type') or v.get('types'))
os.makedirs('data', exist_ok=True)
if ok >= 40:   # 수집이 크게 실패한 날은 기존 파일을 덮어쓰지 않음
    json.dump({'updated': now, 'n': ok, 'fact': F, 'log': src.LOG[-30:]}, open('data/fact.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    json.dump({'updated': now, 'sh': SH, 'kapt': K}, open('data/raw.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print('fact ok', ok)
else:
    print('fact too few', ok); sys.exit(1)
