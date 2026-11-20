"""行情奔跑：數十年週線＋2026 日線，鏡頭鎖住線頭往前跑。
DS 娘站在線頭衝浪；新高噴火花；崩跌時閃電劈下、大字玻璃碎裂；側邊事件卡；2026 段高亮。"""
import datetime as _dt
from eng import *  # noqa
import eng

_WK = json.load(open(R + '/30_data/wk/wk.json'))


def _ord(d): return _dt.date.fromisoformat(d).toordinal()
def _date(o): return _dt.date.fromordinal(int(o))


@functools.lru_cache(16)
def run_rows(sym, d0='1900-01-01', d1='2026-12-31'):
    rows = [r for r in _WK.get(sym, []) if r[0] < '2026-01-01' and d0 <= r[0] <= d1]
    rows += [r for r in OHLC.get(sym, []) if r[0] >= '2026-01-01' and d0 <= r[0] <= d1]
    X = np.array([_ord(r[0]) for r in rows], float)
    A = np.array([r[1:5] for r in rows], float)
    E = np.append(X[1:], X[-1] + 1)  # 每根的結束日
    E[-1] = X[-1] + max(1, (X[-1] - X[-2]) if len(X) > 1 else 1)
    return X, A, E


# ───────────── 玻璃碎裂、閃電、火花 ─────────────
@functools.lru_cache(32)
def _glyph(s, size, col, fk):
    F = font(fk, size); bb = F.getbbox(s); pad = int(size * 0.25)
    im = Image.new('RGBA', (bb[2] - bb[0] + 2 * pad, bb[3] - bb[1] + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((pad - bb[0], pad - bb[1]), s, font=F, fill=col + (255,))
    g = im.filter(ImageFilter.GaussianBlur(size * 0.10)); gl = Image.new('RGBA', im.size, col + (0,)); gl.putalpha(g.getchannel('A').point(lambda v: int(v * 0.9)))
    out = Image.new('RGBA', im.size, (0, 0, 0, 0)); out.alpha_composite(gl); out.alpha_composite(gl); out.alpha_composite(im)
    return out


@functools.lru_cache(32)
def _pieces(s, size, col, fk, seed):
    """把字切成三角玻璃片：[(片圖, 片中心相對字中心, 外緣三角形)]"""
    im = _glyph(s, size, col, fk); w, h = im.size; rnd = random.Random(seed)
    nx, ny = max(4, w // 70), max(3, h // 70)
    P = [[(min(w, max(0, i * w / nx + (rnd.uniform(-0.35, 0.35) * w / nx if 0 < i < nx else 0))),
           min(h, max(0, j * h / ny + (rnd.uniform(-0.35, 0.35) * h / ny if 0 < j < ny else 0)))) for i in range(nx + 1)] for j in range(ny + 1)]
    out = []
    for j in range(ny):
        for i in range(nx):
            a, b, c, d = P[j][i], P[j][i + 1], P[j + 1][i + 1], P[j + 1][i]
            for tri in ((a, b, c), (a, c, d)) if rnd.random() < 0.5 else ((a, b, d), (b, c, d)):
                xs = [p[0] for p in tri]; ys = [p[1] for p in tri]
                bx0, by0, bx1, by1 = int(min(xs)), int(min(ys)), int(math.ceil(max(xs))) + 1, int(math.ceil(max(ys))) + 1
                m = Image.new('L', (bx1 - bx0, by1 - by0), 0); loc = [(p[0] - bx0, p[1] - by0) for p in tri]
                ImageDraw.Draw(m).polygon(loc, fill=255)
                pc = im.crop((bx0, by0, bx1, by1)); pc.putalpha(ImageChops.multiply(pc.getchannel('A'), m))
                if pc.getchannel('A').getbbox() is None: continue
                ImageDraw.Draw(pc).line(loc + [loc[0]], fill=(235, 250, 255, 170), width=2)
                out.append((pc, ((bx0 + bx1) / 2 - w / 2, (by0 + by1) / 2 - h / 2)))
    return out


def shatter(s, xy=(0.5, 0.5), size=260, col=WHITE, t_in=0.0, t_break=1.0, fk='num', seed=1, power=1.0, t_out=None):
    """大字彈入（玻璃光澤），t_break 碎成三角玻璃片往外飛散"""
    def f(x):
        if x.t < t_in or (t_out is not None and x.t > t_out): return
        cx, cy = xy[0] * W, xy[1] * H
        if x.t < t_break:
            q = x.t - t_in; im = _glyph(s, size, col, fk)
            sc = ease(min(1, q / 0.16), 'back') * (1 + 0.03 * max(0, 1 - q / 0.5))
            if sc <= 0.01: return
            im2 = im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc))), Image.BILINEAR)
            # 掃過的反光條
            if q < 0.6:
                sh = Image.new('L', im2.size, 0); xx = int((q / 0.6) * (im2.width + 200)) - 100
                ImageDraw.Draw(sh).polygon([(xx, 0), (xx + 60, 0), (xx - 40, im2.height), (xx - 100, im2.height)], fill=150)
                hl = Image.new('RGBA', im2.size, (255, 255, 255, 0)); hl.putalpha(ImageChops.multiply(sh, im2.getchannel('A')))
                im2 = im2.copy(); im2.alpha_composite(hl)
            eng._safe_comp(x.img, im2, (cx - im2.width / 2, cy - im2.height / 2)); return
        q = x.t - t_break
        if q > 1.1: return
        rnd = random.Random(seed)
        for pc, (ox, oy) in _pieces(s, size, col, fk, seed):
            L = math.hypot(ox, oy) + 1e-3; sp = power * rnd.uniform(500, 1400)
            vx = ox / L * sp + rnd.uniform(-200, 200); vy = oy / L * sp * 0.7 + rnd.uniform(-500, 100)
            px = cx + ox + vx * q; py = cy + oy + vy * q + 1500 * q * q
            rot = rnd.uniform(-540, 540) * q
            p2 = pc.rotate(rot, Image.BILINEAR, expand=True)
            a = max(0.0, 1 - q / 1.1)
            if a < 1: p2 = p2.copy(); p2.putalpha(p2.getchannel('A').point(lambda v: int(v * a)))
            eng._safe_comp(x.img, p2, (px - p2.width / 2, py - p2.height / 2))
    return f


def shards(t0, xy=(0.5, 0.5), n=40, seed=7, col=(220, 245, 255), power=1.0, dur=1.4):
    """空的玻璃碎片（白邊半透明三角）從一點炸開"""
    rnd = random.Random(seed)
    S = [(rnd.uniform(0, 2 * math.pi), rnd.uniform(500, 1500) * power, rnd.uniform(18, 90), rnd.uniform(-600, 600), rnd.random(), rnd.uniform(0.6, 1.0)) for _ in range(n)]
    def f(x):
        q = x.t - t0
        if q < 0 or q > dur: return
        lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
        a = 1 - q / dur
        for ang, sp, sz, rs, r0, al in S:
            px = xy[0] * W + math.cos(ang) * sp * q; py = xy[1] * H + math.sin(ang) * sp * q * 0.75 + 900 * q * q
            th = r0 * 6.28 + math.radians(rs * q)
            pts = [(px + sz * math.cos(th + k * 2.1 + (0.4 if k == 1 else 0)) * (0.6 if k == 2 else 1), py + sz * math.sin(th + k * 2.1) * 0.7) for k in range(3)]
            d.polygon(pts, fill=col + (int(18 * a * al),)); d.line(pts + [pts[0]], fill=col + (int(240 * a * al),), width=2)
        g = lay.resize((W // 4, H // 4)).filter(ImageFilter.GaussianBlur(4)).resize((W, H)); add_light(x.img, g, 1.2)
        x.img.alpha_composite(lay)
    return f


def _bolt(p0, p1, seed, disp=None, depth=7):
    rnd = random.Random(seed); pts = [p0, p1]; disp = disp or math.hypot(p1[0] - p0[0], p1[1] - p0[1]) * 0.28
    for k in range(depth):
        new = [pts[0]]
        for a, b in zip(pts, pts[1:]):
            dx, dy = b[0] - a[0], b[1] - a[1]; L = math.hypot(dx, dy) + 1e-6; off = rnd.uniform(-1, 1) * disp / (2 ** k)
            new += [((a[0] + b[0]) / 2 - dy / L * off, (a[1] + b[1]) / 2 + dx / L * off), b]
        pts = new
    return pts


def lightning(t0, p_end, seed=3, dur=0.55, col=(190, 225, 255), x_top=None):
    """閃電從畫面頂端劈到 p_end（像素），閃兩下後消失；p_end 可為函式 t→(x,y)"""
    rnd = random.Random(seed)
    def f(x):
        q = x.t - t0
        if q < 0 or q > dur: return
        on = 1.0 if q < 0.07 else (0.15 if q < 0.11 else max(0, 1 - (q - 0.11) / (dur - 0.11)))
        if on <= 0.02: return
        pe = p_end(x.t) if callable(p_end) else p_end
        xt = x_top if x_top is not None else pe[0] + random.Random(seed).uniform(-260, 260)
        main = _bolt((xt, -20), pe, seed)
        br = []
        r2 = random.Random(seed + 1)
        for k in range(3):
            i = r2.randint(len(main) // 5, len(main) * 3 // 4); a = main[i]
            br.append(_bolt(a, (a[0] + r2.uniform(-320, 320), a[1] + r2.uniform(120, 360)), seed + 10 + k, depth=5))
        lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
        for pts, wm in [(main, 1.0)] + [(b, 0.45) for b in br]:
            d.line(pts, fill=col + (int(110 * on),), width=int(16 * wm) + 1)
            d.line(pts, fill=(225, 240, 255, int(230 * on)), width=int(6 * wm) + 1)
            d.line(pts, fill=(255, 255, 255, int(255 * on)), width=max(1, int(2.5 * wm)))
        g = lay.resize((W // 4, H // 4)).filter(ImageFilter.GaussianBlur(6)).resize((W, H)); add_light(x.img, g, 1.6 * on)
        x.img.alpha_composite(lay)
        # 落點白光
        r = 90 * on; gl = Image.new('RGBA', (W, H), (0, 0, 0, 0)); ImageDraw.Draw(gl).ellipse((pe[0] - r, pe[1] - r, pe[0] + r, pe[1] + r), fill=(200, 235, 255, int(160 * on)))
        add_light(x.img, gl.filter(ImageFilter.GaussianBlur(30)), 1.5)
    return f


# ───────────── 行情奔跑 ─────────────
def run(sym, keys, d0='1900-01-01', name=None, log=False, box=(80, 290, 1800, 880), head_x=0.58, events=(), eras=(), rider=None,
        hud=True, band2026=True, base=None, title_sub=None, fill=True, cards=True, glow=1.0, lab_years=True, card_life=2.6, crash_xy=(0.33, 0.47), brk=1.35):
    """keys=[(秒, 'YYYY-MM-DD', 視窗天數)]：線頭日期與鏡頭寬度分段內插（寬度用對數內插＝等速拉遠／推近）。
    events=[('YYYY-MM-DD', kind, 文字, 副文字)]：kind='crash'（閃電＋大字碎裂）、'ath'（火花）、'card'（側邊事件卡）、'big'（只出大字）。
    eras=[('YYYY-MM-DD', '時代名')]；rider={'up': 圖, 'dn': 圖, 'h': 0.26}：DS 娘站在線頭。"""
    X, A, E = run_rows(sym, d0)
    O_, Hh, Ll, C_ = A[:, 0], A[:, 1], A[:, 2], A[:, 3]
    K = [(t, _ord(d), w) for t, d, w in keys]
    T = (lambda v: np.log10(np.maximum(v, 1e-9))) if log else (lambda v: v)
    x0, y0, x1, y1 = box; PW, PH = x1 - x0, y1 - y0
    runmax = np.maximum.accumulate(Hh)
    nm = name or NAME.get(sym, sym)
    base_v = base if base is not None else None

    def at(t):
        if t <= K[0][0]: return K[0][1], K[0][2]
        for (ta, da, wa), (tb, db, wb) in zip(K, K[1:]):
            if t <= tb:
                u = ease((t - ta) / max(tb - ta, 1e-6), 'io'); return lerp(da, db, u), math.exp(lerp(math.log(wa), math.log(wb), u))
        return K[-1][1], K[-1][2]

    def t_of(d):
        o = _ord(d)
        for (ta, da, wa), (tb, db, wb) in zip(K, K[1:]):
            if da <= o <= db and db > da:
                # 反解 ease io
                lo, hi = 0.0, 1.0
                for _ in range(30):
                    m = (lo + hi) / 2
                    if lerp(da, db, ease(m, 'io')) < o: lo = m
                    else: hi = m
                return ta + lo * (tb - ta)
        return None

    @functools.lru_cache(512)
    def state(tk):
        t = tk / 1000.0
        hd, win = at(t)
        i = int(np.searchsorted(X, hd, 'right') - 1); i = max(0, min(i, len(X) - 1))
        fr = min(1.0, max(0.0, (hd - X[i]) / max(E[i] - X[i], 1e-6)))
        fr = 1.0 if hd >= E[i] else fr
        o, h, l, c = A[i]; cc = lerp(o, c, ease(fr, 'out'))
        hh = max(o, cc) + (h - max(o, c)) * fr; ll = min(o, cc) - (min(o, c) - l) * fr
        xa = hd - win * head_x; xb = hd + win * (1 - head_x)
        j0 = max(0, int(np.searchsorted(X, xa)) - 1)
        lo = min(np.min(Ll[j0:i]) if i > j0 else ll, ll); hi = max(np.max(Hh[j0:i]) if i > j0 else hh, hh)
        return hd, win, i, fr, (o, hh, ll, cc), xa, xb, T(lo), T(hi)

    def S(t): return state(int(round(t * 1000)))

    def yr(t):
        """y 範圍：前 0.5 秒取樣平均（無狀態，可平行渲染）"""
        a = b = 0.0; n = 6
        for k in range(n):
            s = S(max(K[0][0], t - 0.5 * k / (n - 1)))
            a += s[7]; b += s[8]
        a /= n; b /= n; s0 = S(t); a = min(a, s0[7]); b = max(b, s0[8]); pad = (b - a) * 0.12 + 1e-6
        b2 = b + (b - a + 2 * pad) * (0.62 if rider else 0.0)
        return a - pad, b2 + pad

    def headpos(t):
        hd, win, i, fr, cur, xa, xb, _, _ = S(t); lo, hi = yr(t)
        return (x0 + (hd - xa) / (xb - xa) * PW, y1 - (T(cur[3]) - lo) / (hi - lo) * PH)

    EVT = [(t_of(d), k, s1, s2, d) for d, k, s1, s2 in events]
    EVT = [e for e in EVT if e[0] is not None]

    def f(x):
        t = x.t; hd, win, i, fr, cur, xa, xb, _, _ = S(t); lo, hi = yr(t)
        def PX(o): return x0 + (o - xa) / (xb - xa) * PW
        def PY(v): return y1 - (T(v) - lo) / (hi - lo) * PH
        lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
        # 格線、年份
        for k in range(1, 5):
            yy = y0 + PH * k / 5; d.line((x0, yy, x1, yy), fill=(120, 150, 210, 22), width=1)
            v = (10 ** (hi - (hi - lo) * k / 5)) if log else hi - (hi - lo) * k / 5
            d.text((x1 + 12, yy), fmt(v, 0 if v > 100 else 2), font=font('mono', 22), fill=(120, 140, 180, 150), anchor='lm')
        if lab_years:
            yrs = (xb - xa) / 365.0; st = next(s for s in (1 / 12, 0.25, 1, 2, 5, 10) if yrs / s <= 9)
            y_a = _date(xa).year; y_b = _date(min(xb, _ord('2026-12-31'))).year
            if st < 1:
                for yy_ in range(y_a, y_b + 1):
                    for m in range(1, 13, int(st * 12)):
                        o = _ord(f'{yy_}-{m:02d}-01')
                        if xa < o < xb: d.line((PX(o), y1, PX(o), y1 + 8), fill=(140, 160, 200, 140)); d.text((PX(o), y1 + 14), f'{yy_}.{m:02d}' if m == 1 else f'{m:02d}', font=font('mono', 22), fill=(140, 160, 200, 170), anchor='mt')
            else:
                for yy_ in range(int(math.ceil(y_a / st) * st), y_b + 1, int(st)):
                    o = _ord(f'{yy_}-01-01')
                    if xa < o < xb: d.line((PX(o), y0, PX(o), y1), fill=(120, 150, 210, 18)); d.text((PX(o), y1 + 14), str(yy_), font=font('mono', 24), fill=(140, 160, 200, 180), anchor='mt')
        x.img.alpha_composite(lay)
        # 2026 光帶
        if band2026 and hd > _ord('2026-01-01'):
            bx = max(x0, PX(_ord('2026-01-01'))); ex = min(x1, PX(hd) + 6)
            if ex > bx:
                bl = Image.new('RGBA', (W, H), (0, 0, 0, 0)); bd = ImageDraw.Draw(bl)
                for k in range(12):
                    bd.rectangle((bx, y0 + k * PH / 12, ex, y0 + (k + 1) * PH / 12), fill=UP + (int(8 + 26 * k / 11),))
                bd.line((bx, y0, bx, y1), fill=UP + (200,), width=2)
                if ex - bx > 90: bd.text((bx + 12, y1 - 12), '2026', font=font('num', 54), fill=UP + (235,), anchor='ls')
                x.img.alpha_composite(bl)
        # K 棒
        j0 = max(0, int(np.searchsorted(X, xa)) - 1)
        kl = Image.new('RGBA', (W, H), (0, 0, 0, 0)); kd = ImageDraw.Draw(kl)
        pts = []
        for j in range(j0, i + 1):
            o, h, l, c = (A[j] if j < i else cur)
            px0 = PX(X[j]); px1 = PX(min(E[j], X[j] + (E[j] - X[j]) * (fr if j == i else 1)) if j == i else E[j])
            bw = max(1.0, (PX(E[j]) - PX(X[j])) * 0.62); xm = PX(X[j]) + (PX(E[j]) - PX(X[j])) * 0.5
            col = UP if c >= o else DN
            if j >= 1 and j < i and abs(c / A[j - 1][3] - 1) < 1e-9: col = (180, 180, 190)
            kd.line((xm, PY(h), xm, PY(l)), fill=col + (255,), width=max(1, int(bw / 5)) if bw > 4 else max(1, int(bw)))
            if bw > 2.5:
                ya, yb = sorted((PY(o), PY(c))); kd.rectangle((xm - bw / 2, ya, xm + bw / 2, max(yb, ya + 2)), fill=col + (255,))
            pts.append((xm, PY(c)))
        # 下方漸層面積（顏色看離前高多遠）
        dd = cur[3] / max(runmax[i], 1e-9) - 1
        fc = tuple(int(v) for v in lerpt(UP, DN, float(min(1, max(0, (-dd - 0.03) / 0.12)))))
        if fill and len(pts) > 1:
            m = Image.new('L', (W, H), 0); ImageDraw.Draw(m).polygon(pts + [(pts[-1][0], y1), (pts[0][0], y1)], fill=255)
            gr = Image.linear_gradient('L').resize((W, H)).point(lambda v: int(70 * (1 - v / 255)))
            gr2 = Image.new('L', (W, H), 0); gr2.paste(gr.crop((0, 0, W, PH)).resize((W, PH)), (0, y0))
            fl = Image.new('RGBA', (W, H), fc + (255,)); fl.putalpha(ImageChops.multiply(m, gr2)); x.img.alpha_composite(fl)
            kd.line(pts, fill=(255, 255, 255, 60), width=2)
        g = kl.resize((W // 4, H // 4)).filter(ImageFilter.GaussianBlur(5)).resize((W, H)); add_light(x.img, g, 1.3 * glow)
        x.img.alpha_composite(kl)
        # 前高虛線
        hx, hy = PX(hd), PY(cur[3])
        if dd < -0.03:
            yy = PY(runmax[i])
            if y0 + 12 < yy < y1:
                for xx in range(int(x0), int(x1), 26): d2 = ImageDraw.Draw(x.img); d2.line((xx, yy, xx + 13, yy), fill=GOLD + (190,), width=2)
                ImageDraw.Draw(x.img).text((x0 + 6, yy - 8), f'前高 {fmt(runmax[i])}', font=font('zhb', 26), fill=GOLD + (230,), anchor='ls')
        # 線頭：虛線到軸＋價格框＋光點
        hc = UP if cur[3] >= cur[0] else DN
        d2 = ImageDraw.Draw(x.img)
        for xx in range(int(hx) + 14, int(x1), 18): d2.line((xx, hy, xx + 9, hy), fill=hc + (170,), width=2)
        s_ = fmt(cur[3]); F = font('num', 40); tw = F.getlength(s_)
        d2.rectangle((x1 + 4, hy - 26, x1 + 24 + tw, hy + 26), fill=hc + (255,)); d2.text((x1 + 14, hy), s_, font=F, fill=WHITE + (255,), anchor='lm')
        gl = Image.new('RGBA', (W, H), (0, 0, 0, 0)); gd = ImageDraw.Draw(gl)
        pul = 1 + 0.25 * math.sin(t * 9)
        gd.ellipse((hx - 34 * pul, hy - 34 * pul, hx + 34 * pul, hy + 34 * pul), fill=hc + (120,)); add_light(x.img, gl.filter(ImageFilter.GaussianBlur(16)), 1.4)
        d2.ellipse((hx - 9, hy - 9, hx + 9, hy + 9), fill=WHITE + (255,))
        # 新高火花：接近前高時從線頭持續噴
        near = dd > -0.004
        if near or any(k == 'ath' and 0 <= t - te < 1.2 for te, k, *_ in EVT):
            sp = Image.new('RGBA', (W, H), (0, 0, 0, 0)); sd = ImageDraw.Draw(sp)
            for k in range(46):
                te = math.floor(t * 40) / 40 - k / 40
                if te < K[0][0]: break
                r = random.Random(int(te * 40) * 7 + 3); q = t - te
                ex, ey = headpos(te)
                vx = r.uniform(-420, 260); vy = r.uniform(-760, -160)
                p1 = (ex + vx * q, ey + vy * q + 1100 * q * q); p0 = (ex + vx * (q - 0.03), ey + vy * (q - 0.03) + 1100 * (q - 0.03) ** 2)
                a = max(0, 1 - q / 1.1); cc = [GOLD, (255, 140, 90), WHITE, UP][r.randint(0, 3)]
                sd.line((p0, p1), fill=cc + (int(255 * a),), width=3)
            add_light(x.img, sp.filter(ImageFilter.GaussianBlur(3)), 1.5); x.img.alpha_composite(sp)
        # DS 娘站在線頭
        if rider:
            slope = cur[3] / max(A[max(0, i - 3)][3], 1e-9) - 1
            pth = rider['up'] if slope >= -0.01 else rider['dn']
            hpx = int(rider.get('h', 0.26) * H); spr, pad = eng._sprite(pth, hpx, OL, None, rider.get('flip', False))
            ang = max(-16, min(16, slope * 400)) * (1 if rider.get('tilt', True) and slope >= -0.01 else 0)
            sp2 = spr.rotate(ang, Image.BICUBIC, expand=True) if ang else spr
            bob = 6 * math.sin(t * 5.1)
            eng._safe_comp(x.img, sp2, (hx - sp2.width / 2, hy - sp2.height + pad * 0.6 + 8 + bob))
        # 事件：閃電、碎字、事件卡
        for te, k, s1, s2, dte in EVT:
            q = t - te
            if k == 'crash' and 0 <= q < 0.6:
                lightning(te, (hx, hy), seed=int(te * 100))(x)
                if q < 0.5:  # 綠色粒子往兩側噴
                    sp = Image.new('RGBA', (W, H), (0, 0, 0, 0)); sd = ImageDraw.Draw(sp); r = random.Random(int(te * 13))
                    for _ in range(120):
                        ang = r.uniform(-0.35, 0.35) + (math.pi if r.random() < 0.5 else 0); v = r.uniform(300, 1300)
                        px_ = hx + math.cos(ang) * v * q; py_ = hy + math.sin(ang) * v * q * 0.5 + r.uniform(-12, 12)
                        sd.rectangle((px_, py_, px_ + 3, py_ + 3), fill=(120, 255, 190, int(255 * (1 - q / 0.5))))
                    add_light(x.img, sp.filter(ImageFilter.GaussianBlur(2)), 1.6); x.img.alpha_composite(sp)
            if k in ('crash', 'big') and 0 <= q < brk + 1.2 and s1:
                colb = DN if s1.startswith('-') else UP
                shatter(s1, crash_xy, 250, colb, t_in=te, t_break=te + brk, seed=int(te * 10) % 97)(x)
                shards(te, (hx / W, hy / H), n=34, seed=int(te * 7), power=0.9)(x)
                if s2 and q < brk: txt(s2, (crash_xy[0], crash_xy[1] + 0.16), 56, 'zh', WHITE, t_in=te + 0.1, anim='rise')(x)
        # HUD
        if hud:
            hd_ = ImageDraw.Draw(x.img)
            hd_.text((70, 52), nm, font=font('zh', 46), fill=WHITE + (255,), anchor='ls')
            tw0 = font('zh', 46).getlength(nm)
            if title_sub: hd_.text((80 + tw0, 50), title_sub, font=font('mono', 22), fill=(150, 165, 200, 220), anchor='ls')
            v = cur[3]; sv = fmt(v, 2 if v < 1000 else 0)
            col_v = UP if (base_v is None or v >= base_v) and dd > -0.03 else (DN if dd < -0.03 else UP)
            gF = font('num', 128); hd_.text((64, 64), sv, font=gF, fill=col_v + (255,), anchor='la')
            vw = gF.getlength(sv)
            dstr = _date(hd).strftime('%Y.%m.%d'); hd_.text((68, 196), dstr, font=font('num', 62), fill=WHITE + (255,), anchor='la')
            era = None
            for ed, en in eras:
                if hd >= _ord(ed): era = en
            if era:
                dw = font('num', 62).getlength(dstr)
                hd_.line((84 + dw, 204, 84 + dw, 250), fill=GOLD + (255,), width=4); hd_.text((98 + dw, 200), era, font=font('zh', 44), fill=GOLD + (255,), anchor='la')
            if dd < -0.03:
                jj = int(np.argmax(Hh[:i + 1])); ref, rv = f'較 {_date(X[jj]).strftime("%Y.%m.%d")} 高點', dd
            else:
                jj = int(np.argmin(Ll[:i + 1][max(0, j0 - 400):])) + max(0, j0 - 400); ref, rv = f'較 {_date(X[jj]).strftime("%Y.%m.%d")} 低點', cur[3] / Ll[jj] - 1
            bx_ = 64 + vw + 26
            hd_.text((bx_, 92), ref, font=font('zhb', 26), fill=(190, 200, 225, 230), anchor='la')
            cb = DN if rv < 0 else UP; s3 = ('▼ ' if rv < 0 else '▲ ') + f'{rv * 100:+.2f}%'.replace('+', '+' if rv >= 0 else '')
            F3 = font('zhb', 40); w3 = F3.getlength(s3)
            bl_ = Image.new('RGBA', (W, H), (0, 0, 0, 0)); ImageDraw.Draw(bl_).rectangle((bx_, 128, bx_ + w3 + 24, 182), fill=cb + (55,)); x.img.alpha_composite(bl_)
            hd_.text((bx_ + 12, 155), s3, font=F3, fill=cb + (255,), anchor='lm')
        # 側邊事件卡（最新在上，最多 3 張）
        if cards:
            live = [(te, s1, s2, dte) for te, k, s1, s2, dte in EVT if k == 'card' and te <= t < te + card_life][-3:]
            yy = 280
            for n_, (te, s1, s2, dte) in enumerate(reversed(live)):
                q = t - te; u = ease(min(1, q / 0.28), 'out'); xo = (1 - u) * 520
                a = int(255 * (1.0 if n_ == 0 else 0.55) * min(1, max(0, (te + card_life - t) / 0.3)))
                cl = Image.new('RGBA', (W, H), (0, 0, 0, 0)); cd = ImageDraw.Draw(cl)
                bx0 = 1340 + xo; hgt = 150 if s2 else 110
                cd.rectangle((bx0, yy, bx0 + 450, yy + hgt), fill=(8, 12, 26, int(a * 0.82)))
                cc = UP if (s2 or '').startswith('+') else (DN if (s2 or '').startswith('-') else GOLD)
                cd.rectangle((bx0, yy, bx0 + 8, yy + hgt), fill=cc + (a,))
                cd.text((bx0 + 28, yy + 14), _date(_ord(dte)).strftime('%Y.%m.%d'), font=font('num', 34), fill=(200, 210, 230, a), anchor='la')
                cd.text((bx0 + 28, yy + 52), s1, font=font('zh', 44), fill=WHITE + (a,), anchor='la')
                if s2: cd.text((bx0 + 28, yy + 106), s2, font=font('zhb', 32), fill=cc + (a,), anchor='la')
                x.img.alpha_composite(cl); yy += hgt + 18
    f.t_of = t_of; f.headpos = headpos; f.events = EVT
    return f
