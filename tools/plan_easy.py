# -*- coding: utf-8 -*-
"""쉬운 평면도 — CAD 도면(치수선·글자가 작아 폰에서 못 읽는 SH 단위세대 평면도)만 있는 단지를 Claude가 다시 그린 것.
2026-11-26 사용자: "이런 평면도만 있을경우에 너가 쉬운 버전으로 다시 그려".

입력: data/plan_easy.json {items: {원본 평면도 URL: {ty, m2, name, src, grid: 원본 도면 치수 메모, rooms, doors, wins, notes}}}
  좌표는 원본 도면의 벽 중심선 치수(mm) — 왼쪽 위가 (0, 0), 오른쪽이 +x, 아래가 +y. 방 크기 글자(w·h)는 도면의 안목 치수가 있으면 그것.
  rooms: [{t 이름, k 종류(live·kit·bed·bath·entry·balc·util·out·fix 붙박이), x, y, w, h, sz: [안목 가로, 세로](없으면 그림 크기), open: 위/아래 트임('T'·'B'·'L'·'R' — 그 변은 벽 대신 점선)}]
  opens: [[x1, y1, x2, y2], ...] — 벽 없이 트인 곳(벽을 지우고 점선)
  doors: [{x, y(경첩), dx, dy(닫힌 문짝 방향 단위 벡터 × 폭), sx, sy(열리는 쪽 단위 벡터)}] — 문짝이 열리는 호로 그림
  wins: [[x1, y1, x2, y2], ...] — 벽 위 창(하늘색 두 줄) · slides: [[x1, y1, x2, y2], ...] — 미닫이문(엇갈린 두 줄)
결과: data/plan_easy/<원본 URL 해시 16자>.svg + data/plan_easy/index.json {URL: 파일}
화면(index.html)은 SH 단지 상세의 사진 띠에서 원본 평면도 앞에 '쉬운 평면도'로 넣음(원본도 그대로 있음)."""
import hashlib, html, json, math, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'data', 'plan_easy.json')
OUT = os.path.join(ROOT, 'data', 'plan_easy')
FONT = "'Apple SD Gothic Neo','Malgun Gothic','Noto Sans KR','Noto Sans CJK KR',sans-serif"
FILL = {'live': '#FCE9CC', 'kit': '#FCE9CC', 'bed': '#D9E8F8', 'bath': '#CFEFEA', 'entry': '#E6E9ED', 'balc': '#E3F2D9', 'util': '#F1F1F1', 'out': '#F6F6F4', 'fix': '#EEE6D8'}
INK, WALL, WIN, MUTED = '#1F2328', '#2B3036', '#2E9BE6', '#69707A'


def key(u):
    return hashlib.sha1(u.encode('utf-8')).hexdigest()[:16]


def esc(s):
    return html.escape(str(s), quote=True)


def m(v):
    return '%.1f' % (v / 1000)


def cw(ch, fs):   # 글자 폭 어림(한글·한자 = 글자 크기, 영숫자 0.58, 빈칸 0.3)
    o = ord(ch)
    return fs * (0.3 if ch == ' ' else 0.58 if o < 0x2E80 and o not in (0x33A1, 0x00D7) else 1.0)


def wrap(s, fs, maxw):
    out, cur, curw = [], '', 0.0
    for tok in str(s).replace(' · ', ' ·\u0001').replace('\u0001', ' ').split(' '):
        tw = sum(cw(c, fs) for c in tok)
        sp = cw(' ', fs) if cur else 0
        if cur and curw + sp + tw > maxw:
            out.append(cur); cur, curw = tok, tw
        else:
            cur = (cur + ' ' + tok) if cur else tok; curw += sp + tw
    if cur:
        out.append(cur)
    return out


def area(w, h):
    a = w * h / 1e6
    return '%.1f㎡·%.1f평' % (a, a / 3.3058)


def text(x, y, s, size, weight=700, fill=INK, anchor='middle'):
    return f'<text x="{x:.0f}" y="{y:.0f}" font-size="{size:.0f}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}" font-family="{FONT}">{esc(s)}</text>'


def svg(it):
    rooms = it['rooms']
    body = [r for r in rooms if r['k'] not in ('out', 'fix')]
    X0 = min(r['x'] for r in body); X1 = max(r['x'] + r['w'] for r in body)
    Y0 = min(r['y'] for r in rooms); Y1 = max(r['y'] + r['h'] for r in body)
    W = X1 - X0
    pad = 520
    maxw = W + 2 * pad - 2 * 200
    sumL = wrap(it.get('sum', ''), 210, maxw)
    noteL = [l for n in (it.get('notes') or []) for l in wrap(n, 175, maxw)]
    head = 1000 + 290 * len(sumL)
    foot = 760 + 270 * len(noteL)
    vx, vy, vw, vh = X0 - pad, Y0 - head, W + 2 * pad, (Y1 - Y0) + head + foot + 320
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vx:.0f} {vy:.0f} {vw:.0f} {vh:.0f}" width="{vw / 10:.0f}" height="{vh / 10:.0f}">',
         f'<rect x="{vx:.0f}" y="{vy:.0f}" width="{vw:.0f}" height="{vh:.0f}" fill="#FFFFFF"/>']
    # 머리: 제목 · 한 줄 요약
    o.append(text(X0 - pad + 200, Y0 - head + 360, f"{it['name']} {it['ty']}형 — 쉬운 평면도", 300, 800, INK, 'start'))
    for i_, l in enumerate(sumL):
        o.append(text(X0 - pad + 200, Y0 - head + 720 + 290 * i_, l, 210, 600, MUTED, 'start'))
    # 방 바탕
    for r in rooms:
        dash = ' stroke-dasharray="60 50"' if r['k'] == 'out' else ''
        if r['k'] == 'fix':
            continue
        o.append(f'<rect x="{r["x"]}" y="{r["y"]}" width="{r["w"]}" height="{r["h"]}" fill="{FILL.get(r["k"], "#fff")}" stroke="{"#B9BEC4" if r["k"] == "out" else "none"}" stroke-width="30"{dash}/>')
    for r in rooms:   # 붙박이(조리대 등): 벽 없이 옅은 칸
        if r['k'] == 'fix':
            o.append(f'<rect x="{r["x"] + 45}" y="{r["y"] + 45}" width="{r["w"] - 45}" height="{r["h"] - 45}" fill="{FILL["fix"]}" stroke="#B8AA94" stroke-width="20"/>')
    # 벽: 방마다 네 변(트인 변은 점선)
    for r in body:
        x, y, w, h = r['x'], r['y'], r['w'], r['h']
        sides = {'T': (x, y, x + w, y), 'B': (x, y + h, x + w, y + h), 'L': (x, y, x, y + h), 'R': (x + w, y, x + w, y + h)}
        for s_, (a, b, c, d) in sides.items():
            if s_ in (r.get('open') or ''):
                o.append(f'<line x1="{a}" y1="{b}" x2="{c}" y2="{d}" stroke="#9AA2AC" stroke-width="28" stroke-dasharray="90 80"/>')
            else:
                o.append(f'<line x1="{a}" y1="{b}" x2="{c}" y2="{d}" stroke="{WALL}" stroke-width="{70 if r["k"] in ("balc", "util") else 90}" stroke-linecap="square"/>')
    # 트인 곳(벽 없이 이어진 곳): 벽을 바탕색으로 지우고 점선
    for op in it.get('opens') or []:
        x1, y1, x2, y2 = op[:4]
        o.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{FILL[op[4] if len(op) > 4 else "live"]}" stroke-width="110"/>')
        o.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#9AA2AC" stroke-width="28" stroke-dasharray="90 80"/>')
    # 창(벽 위 하늘색 두 줄)
    for x1, y1, x2, y2 in it.get('wins') or []:
        o.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#FFFFFF" stroke-width="150"/>')
        o.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{WIN}" stroke-width="130"/>')
        o.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#FFFFFF" stroke-width="40"/>')
    # 문(벽을 비우고 열리는 호)
    for d in it.get('doors') or []:
        hx, hy, dx, dy, sx, sy = d['x'], d['y'], d['dx'], d['dy'], d['sx'], d['sy']
        wdt = math.hypot(dx, dy)
        ex, ey = hx + dx, hy + dy                        # 닫힌 문짝 끝
        ox, oy = hx + sx * wdt, hy + sy * wdt            # 열린 문짝 끝
        o.append(f'<line x1="{hx}" y1="{hy}" x2="{ex}" y2="{ey}" stroke="#FFFFFF" stroke-width="120"/>')
        cross = dx * sy - dy * sx
        o.append(f'<path d="M{ex:.0f} {ey:.0f} A{wdt:.0f} {wdt:.0f} 0 0 {1 if cross > 0 else 0} {ox:.0f} {oy:.0f}" fill="none" stroke="#7A8592" stroke-width="22" stroke-dasharray="50 35"/>')
        o.append(f'<line x1="{hx}" y1="{hy}" x2="{ox:.0f}" y2="{oy:.0f}" stroke="{WALL}" stroke-width="40"/>')
    # 미닫이(옆으로 미는 문): 벽을 비우고 엇갈린 문짝 두 줄
    for x1, y1, x2, y2 in it.get('slides') or []:
        L = math.hypot(x2 - x1, y2 - y1) or 1; ux, uy = (x2 - x1) / L, (y2 - y1) / L; nx, ny = -uy * 35, ux * 35
        o.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#FFFFFF" stroke-width="120"/>')
        o.append(f'<line x1="{x1 + nx:.0f}" y1="{y1 + ny:.0f}" x2="{x1 + ux * L * 0.58 + nx:.0f}" y2="{y1 + uy * L * 0.58 + ny:.0f}" stroke="{WALL}" stroke-width="34"/>')
        o.append(f'<line x1="{x2 - nx:.0f}" y1="{y2 - ny:.0f}" x2="{x2 - ux * L * 0.58 - nx:.0f}" y2="{y2 - uy * L * 0.58 - ny:.0f}" stroke="{WALL}" stroke-width="34"/>')
    # 이름·크기 글자
    for r in rooms:
        x, y, w, h = r['x'], r['y'], r['w'], r['h']
        cx, cy = x + w / 2 + r.get('dx', 0), y + h / 2 + r.get('dy', 0)
        small = min(w, h) < 1300
        big = 330 if not small else 230
        if r['k'] == 'fix':
            o.append(text(cx, cy + 55, r['t'], 150, 700, '#6B5E4A'))
            continue
        sz = r.get('sz') or ([w, h] if r['k'] not in ('out',) else None)
        lines = [(r['t'], big, 800, INK)]
        if r.get('sub'):
            lines.append((r['sub'], 190 if not small else 165, 600, MUTED))
        if sz and not r.get('nosz'):
            lines.append((f'{m(sz[0])}×{m(sz[1])}m', 205 if not small else 170, 700, '#3B4350'))
            if not small or r.get('ar'):
                lines.append((area(sz[0], sz[1]), 190, 600, MUTED))
        tot = sum(l[1] * 1.22 for l in lines)
        yy = cy - tot / 2 + lines[0][1]
        for s_, fs, fw, col in lines:
            o.append(text(cx, yy, s_, fs, fw, col))
            yy += fs * 1.22
    # 아래: 축척 막대 · 메모
    by = Y1 + 420
    o.append(f'<line x1="{X0}" y1="{by}" x2="{X0 + 1000}" y2="{by}" stroke="{INK}" stroke-width="40"/>')
    o.append(f'<line x1="{X0}" y1="{by - 80}" x2="{X0}" y2="{by + 80}" stroke="{INK}" stroke-width="30"/><line x1="{X0 + 1000}" y1="{by - 80}" x2="{X0 + 1000}" y2="{by + 80}" stroke="{INK}" stroke-width="30"/>')
    o.append(text(X0 + 1150, by + 70, '1m', 200, 700, INK, 'start'))
    o.append(f'<line x1="{X0 + 1800}" y1="{by}" x2="{X0 + 2500}" y2="{by}" stroke="#FFFFFF" stroke-width="150"/><line x1="{X0 + 1800}" y1="{by}" x2="{X0 + 2500}" y2="{by}" stroke="{WIN}" stroke-width="130"/><line x1="{X0 + 1800}" y1="{by}" x2="{X0 + 2500}" y2="{by}" stroke="#FFFFFF" stroke-width="40"/>')
    o.append(text(X0 + 2620, by + 70, '창', 200, 700, INK, 'start'))
    o.append(f'<path d="M{X0 + 3300} {by + 90} A350 350 0 0 1 {X0 + 3650} {by - 260}" fill="none" stroke="#7A8592" stroke-width="22" stroke-dasharray="50 35"/><line x1="{X0 + 3300}" y1="{by + 90}" x2="{X0 + 3300}" y2="{by - 260}" stroke="{WALL}" stroke-width="40"/>')
    o.append(text(X0 + 3780, by + 70, '문', 200, 700, INK, 'start'))
    ny = by + 430
    for n in noteL:
        o.append(text(X0 - pad + 200, ny, n, 175, 600, MUTED, 'start'))
        ny += 270
    o.append('</svg>')
    return '\n'.join(o)


def main():
    src = json.load(open(SRC, encoding='utf-8'))
    os.makedirs(OUT, exist_ok=True)
    idx = {}
    for u, it in (src.get('items') or {}).items():
        f = 'data/plan_easy/%s.svg' % key(u)
        open(os.path.join(ROOT, f), 'w', encoding='utf-8').write(svg(it))
        idx[u] = f
    json.dump({'updated': src.get('updated'), 'items': idx}, open(os.path.join(OUT, 'index.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(len(idx), 'plans')


if __name__ == '__main__':
    main()
