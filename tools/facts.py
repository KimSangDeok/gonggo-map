# 단지 사실정보(FACT) 생성: SH 주택정보(houseinfo) + K-apt 공동주택관리정보시스템에서 2026-10-26에 조회한 값
import json, re
SH = {}
K = {}
def load(sh, k):
    SH.clear(); SH.update(sh); K.clear(); K.update(k)
IMG = 'https://www.i-sh.co.kr/houseinfo'
def img(p): return IMG + p
MAP = {
 "방화스카이포레": (["30179"], ["A10021043"]), "이문 아이파크 자이": (["70606"], ["A10020344"]),
 "e편한세상 청계센트럴포레": (["70498"], ["A10024042"]), "목동센트럴아이파크위브": (["70472"], ["A10024872"]),
 "이든채": (["79302"], ["A10025649"]), "아크로타워스퀘어": (["70375"], ["A10026816"]),
 "천왕이펜하우스8단지": (["30141"], ["A10026039"]), "항동 하버라인": (["30156"], ["A10025564"]),
 "천왕이펜하우스7": (["22337"], ["A10027764"]), "천왕연지마을1": (["30137"], ["A10026729"]), "천왕연지마을2": (["30138"], ["A10021128"]),
 "마포더클래시": (["70540"], ["A10023508"]), "공덕동 크로시티": (["90240"], ["A10023118"]), "마포자이더센트리지": (["70409"], ["A10026036"]),
 "e편한세상신촌": (["70360"], ["A10026370"]), "홍제센트럴아이파크": (["70410"], ["A10025767"]), "래미안루센티아": (["70449"], ["A10024938"]),
 "힐스테이트신촌": (["70477"], ["A10024719"]), "북한산두산위브": (["70447"], ["A10025166"]), "대치르엘": (["70505"], ["A10024102"]),
 "고덕온빛채": (["30160"], ["A10020628"]), "강동리엔파크14단지": (["30168"], ["A10024412"]), "강동리엔파크11단지": (["30166"], ["A10024420"]),
 "푸르내": (["79304"], ["A10024487"]), "왕십리자이": (["70374"], ["A10026900"]), "서울숲리버뷰자이": (["70390"], ["A10026207"]),
 "꿈의숲코오롱하늘채": (["70373"], ["A10026571"]), "래미안길음센터피스": (["70430"], ["A10025638"]), "꿈의숲아이파크": (["70480"], ["A10024488"]),
 "보문파크뷰자이": (["70361"], ["A10027189"]), "래미안장위퍼스트하이": (["70437"], ["A10025245"]), "장위자이레디언트": (["70598"], ["A10020716"]),
 "창경궁롯데캐슬시그니처": ([], []), "송파시그니처롯데캐슬": (["70501"], ["A10023887"]), "e편한세상송파파크센트럴": (["70469"], ["A10024787"]),
 "용산롯데캐슬센터포레": (["70433"], ["A10025533"]), "용산센트럴파크 헤링턴스퀘어": (["70470"], ["A10024691"]), "경희궁자이": (["70371"], ["A10026946"]),
 "신내 글로리움": (["22322"], ["A10025137"]), "신내3-3 도시형생활주택": (["30140"], []), "신내3-4 도시형생활주택": ([], []),
 "래미안베라힐즈": (["70408"], ["A10025846"]), "은뜨락": (["79301"], ["A10025677"]), "힐스테이트녹번역": (["70482"], ["A10024313"]),
 "백련산해모로": (["70453"], ["A10024947"]), "DMCSK뷰": (["70522"], ["A10024086"]),
 "마곡엠밸리 1~15단지": (["22211","22213","22215","22217","22219","22221","22223","22225","22227","22229","22231","22233","22237","22239"], None),
 "마곡지구 9단지": (["22227"], ["A10024426"]),
 "마곡수명산파크 1~7단지": (["20438","20439","20440","20441","20442","20443","20444"], None),
 "신정이펜하우스 1~5단지": (["20594","20595","20596","20597","20598"], None),
 "신정숲속마을": (["22342"], None),   # SH 주택정보 이름 '신정4지구 보금자리주택' (양천구 신정로 110)
 "상암월드컵파크 9~12단지": (["20564","20563","20561","20562"], None),
 "천왕이펜하우스 1~6단지": (["20448","20449","20450","20451","20452","20453"], None),
 "천왕연지타운 1,2단지": (["20646","20647"], None),
 "항동하버라인 2·3·4·8단지": (["22271","22275"], ["A10025387","A10025614","A10025302","A10025858"]),
}
BAD_KAPT = {"A10023709"}  # SH 관리비 조인 오류(DMC금호리첸시아)로 확인된 코드

def kapt_of(cds, kapts):
    if kapts is not None: return kapts
    out = []
    for cd in cds:
        k = SH.get(cd, {}).get('kapt')
        if k and k not in BAD_KAPT and k in K and k not in out: out.append(k)
    return out

def base(sp):  # '49S' -> '49', '39A' -> '39'
    m = re.match(r'(\d+)', sp); return m.group(1) if m else sp

def kapt_summary(codes):
    ks = [K[c] for c in codes if c in K]
    if not ks: return None
    o = {'n': len(ks), 'names': [k['nm'] for k in ks]}
    yrs = sorted(k['use'][:7].replace('-', '.') for k in ks if k.get('use'))
    o['built'] = yrs[0] if len(set(yrs)) == 1 else (yrs[0] + '~' + yrs[-1])
    o['hh'] = sum(k['hh'] or 0 for k in ks); o['dong'] = sum(k['dong'] or 0 for k in ks)
    def mode(key):
        vals = [k[key] for k in ks if k.get(key) and k[key] not in ('-', '기타')]
        return max(set(vals), key=vals.count) if vals else None
    o['heat'] = mode('heat'); o['hall'] = mode('hall'); o['apt'] = mode('apt'); o['str'] = mode('str')   # 주택유형(아파트 등)·구조 — K-apt 등록값
    pk = [(k['pg'] or 0, k['pu'] or 0, k['hh'] or 0, int(k['cars']) if (k.get('cars') or '').isdigit() else None, int(k['ev']) if (k.get('ev') or '').isdigit() else None) for k in ks]
    pk = [p for p in pk if (p[0] + p[1]) > 0 and p[2] > 0]
    if pk:
        tot = sum(p[0] + p[1] for p in pk); hh = sum(p[2] for p in pk); under = sum(p[1] for p in pk)
        o['park'] = {'g': sum(p[0] for p in pk), 'u': under, 't': tot, 'per': round(tot / hh, 2), 'under': round(under / tot * 100)}
        pers = [round((p[0] + p[1]) / p[2], 2) for p in pk]
        if len(pk) > 1: o['park']['per_rng'] = [min(pers), max(pers)]
        cars = [p for p in pk if p[3] is not None and p[3] > 0]
        if cars:
            o['park']['cars'] = sum(p[3] for p in cars); o['park']['cars_per'] = round(sum(p[3] for p in cars) / sum(p[0] + p[1] for p in cars) * 100)
            ev = [p[4] for p in cars if p[4] is not None]
            if ev: o['park']['ev'] = sum(ev)
    else:
        o['park'] = None
    o['elev'] = sum(k['elev'] or 0 for k in ks) or None
    return o

def near_cost(sh, area):
    best = None
    for a, won in sh.get('cost') or []:
        d = abs(float(a) - area)
        if best is None or d < best[0]: best = (d, won)
    return (best[1], sh.get('costYm')) if best and best[0] < 1.0 else (None, None)

FACT = {}
import itertools
def facts_for(name, m2=None, kind='행복주택'):
    cds, kapts = MAP.get(name, ([], []))
    kcodes = kapt_of(cds, kapts)
    o = {'src': []}
    shs = [SH[c] for c in cds if c in SH]
    if shs: o['src'].append('SH 주택정보 ' + (max(t[10] for s in shs for t in s['types']) if any(s['types'] for s in shs) else '2026.10'))
    if kcodes: o['src'].append('K-apt')
    photos = [img(p) for s in shs for p in s.get('imgs', [])][:3]
    if photos: o['photos'] = photos
    # 실내 각 방 사진(SH 주택정보 사진유형 07). 캡션(imgNm)이 없으면 파일명에서 라벨을 만들고, 캡션/파일명에 형 숫자가 있으면(예: '39A 안방', '36형거실', '(49B)', '거실-44') 이 형 것만 우선
    import re as _re
    def _clean(cap, path):
        if cap and cap.strip(): return cap.strip()
        fn = path.rsplit('/', 1)[-1]
        fn = _re.sub(r'^\d{14,20}_\d+_', '', fn); fn = _re.sub(r'\.[A-Za-z]+$', '', fn)
        fn = _re.sub(r'\[(크기변환|꾸미기)\]|사본\s*-|포맷변환_|KakaoTalk_\d+_\d+(_\d+)?|Resized_\d+|temp_[\d.]+|일괄편집_', ' ', fn)
        fn = _re.sub(r'\d{3}-\d{3,4}\(([^)]*)\)\d{6,}', r'(\1)', fn)   # 202-1104(39A)221017039 → (39A)
        fn = _re.sub(r'\d{6,}', ' ', fn); fn = _re.sub(r'\[[^\]]*\]', ' ', fn)
        fn = _re.sub(r'\s+', ' ', fn).strip(' _-')
        if _re.fullmatch(r'\d{2}', fn): fn += '형'
        return fn or '실내'
    def _ty(cap):
        for pat in (r'(\d{2})\s*형', r'(\d{2})\s*타입', r'\((\d{2})[A-Z]?\'?-?\d?\)', r'(?:^|\s)(\d{2})[A-Z]?\d?(?=\s|$)', r'-\s*(\d{2})(?=\s|$)'):
            m = _re.search(pat, cap or '')
            if m and 15 <= int(m.group(1)) <= 90: return m.group(1)
        return None
    want = str(int(m2)) if m2 else None
    rooms_all = []
    for s in shs:
        for cap, path in s.get('rooms', []) or []:
            lab = _clean(cap, path); ty = _ty(lab) or _ty(path.rsplit('/', 1)[-1])
            if _re.fullmatch(r'\d{2}', lab): lab += '형'
            if lab == '실내' and ty: lab = ty + '형 실내'
            rooms_all.append({'t': lab, 'u': img(path), 'ty': ty})
    if rooms_all:
        typed = [r for r in rooms_all if r['ty']]
        if want and typed:
            mine = [r for r in typed if r['ty'] == want]
            pick = mine or [r for r in rooms_all if not r['ty']] or rooms_all
            o['rooms_mine'] = bool(mine)
        else:
            pick = rooms_all
        o['rooms'] = [{'t': r['t'], 'u': r['u']} for r in pick[:24]]
        o['rooms_n'] = len(rooms_all); o['rooms_k'] = len(pick)
    pts = sorted({t for s in shs for t in (s.get('phototypes') or [])})
    if pts: o['phototypes'] = pts
    cyber = [c for s in shs for c in (s.get('cyber') or [])]
    if cyber: o['cyber'] = cyber[:4]
    subs = next((s['subway'] for s in shs if s.get('subway')), None)
    if subs: o['subway'] = subs[:2]
    ks = kapt_summary(kcodes)
    if ks: o['k'] = ks
    if kind == '행복주택' and shs and m2:
        sh = shs[0]
        cands = [t for t in sh['types'] if t[1] != '장기전세']
        exact = [t for t in cands if abs(t[2] - m2) < 0.6]
        pool = exact or cands
        if pool:
            pool.sort(key=lambda t: (abs(t[2] - m2), 'S' in t[0]))
            t = pool[0]
            o['type'] = {'sp': t[0], 'cls': t[1], 'ar': t[2], 'hh': t[3], 'rooms': t[4], 'vac': t[5], 'out': t[7], 'ym': t[10], 'exact': bool(exact)}
            plan = sh['plans'].get(t[0]) or next((v for k2, v in sh['plans'].items() if base(k2) == base(t[0])), None)
            if plan: o['plan'] = img(plan)
            won, ym = near_cost(sh, t[2])
            if won: o['cost'] = {'won': won, 'ym': ym}
    if kind == '국민임대' and shs:
        T = {}
        for s in shs:
            for t in s['types']:
                if t[1] != '국민임대': continue
                b = base(t[0])
                if b not in ('39', '49', '59'): continue
                d = T.setdefault(b, {'hh': 0, 'vac': 0, 'out': 0, 'rooms': None, 'n': 0, 'cost': [], 'plan': None, 'ym': t[10]})
                d['hh'] += t[3]; d['vac'] += t[5]; d['out'] += t[7]; d['n'] += 1
                if d['rooms'] is None and t[4]: d['rooms'] = t[4]
                won, ym = near_cost(s, t[2])
                if won: d['cost'].append(won); d['cost_ym'] = ym
                if not d['plan']:
                    p = s['plans'].get(t[0]) or next((v for k2, v in s['plans'].items() if base(k2) == b), None)
                    if p: d['plan'] = img(p)
        for b, d in T.items():
            if d['cost']: d['cost'] = [min(d['cost']), max(d['cost'])]
            else: d.pop('cost')
        if T: o['types'] = T
    if shs and all(s.get('phototypes') is not None and not s.get('phototypes') for s in shs) and not (o.get('photos') or o.get('rooms') or o.get('plan') or any(d.get('plan') for d in (o.get('types') or {}).values())):
        o['nophoto'] = True   # SH 주택정보에 사진 유형이 하나도 없고 평면도도 없는 단지 (사진유형 목록까지 조회한 데이터에서만 판단)
    return o

