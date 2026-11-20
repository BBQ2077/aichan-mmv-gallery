"""海面線圖（v4）：價格就是海面。
- sea()：2026 日 K，固定寬度，一根一根在唱到的字上長出；收盤連成海面，下方是海水（實拍水下光紋＋氣泡）；
  天空是 Muse 背景，依劇情換景；DS 娘站在線頭前方的浪裡，只在事件點換姿勢。
- longsea()：數十年月線當海面，鏡頭沿時間推進或從 2026 拉遠；歷史事件釘在浪谷。"""
import bisect
from eng import *  # noqa
import eng
from eng_run import lightning, shards, shatter
from eng_long import long_rows

YG = np.arange(H, dtype=np.float32)[:, None]
XG = np.arange(W, dtype=np.float32)
_spr = functools.lru_cache(48)(eng._sprite)
C2 = lambda n: f'10_img/cut2/{n}.png'
OLR = ((255, 255, 255), 8), ((8, 22, 60), 7)


# ───────────── 天空 ─────────────
@functools.lru_cache(12)
def _sky(name, z=1.14):
    im = img(f'10_img/muse/{name}.png').convert('RGB')
    s = max(W * z / im.width, H * z / im.height)
    return im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)


def _sky_crop(name, shift, dy=0.0):
    im = _sky(name)
    mx, my = im.width - W, im.height - H
    x0 = int(min(max(mx / 2 + shift, 0), mx)); y0 = int(min(max(my * (0.5 + dy), 0), my))
    return im.crop((x0, y0, x0 + W, y0 + H))


def sky_paint(x, keys, shift=0.0, dark=0.3, flash=0.0, dy=0.0):
    """keys=[(t, 'sky_dawn')]：到 t 換景，0.6 秒交叉溶接"""
    cur = keys[0][1]; prev = None; u = 1.0
    for t0, nm in keys:
        if x.t >= t0: prev, cur = cur, nm; u = min(1.0, (x.t - t0) / 0.6)
    im = _sky_crop(cur, shift, dy)
    if prev and prev != cur and u < 1: im = Image.blend(_sky_crop(prev, shift, dy), im, ease(u, 'io'))
    if dark > 0: im = Image.blend(im, Image.new('RGB', (W, H), (2, 6, 18)), dark)
    if flash > 0: im = Image.blend(im, Image.new('RGB', (W, H), (225, 240, 255)), min(0.8, flash))
    x.img.paste(im.convert('RGBA'))


# ───────────── 海水 ─────────────
def _caus(t, speed=1.0):
    fs = eng._vid_frames('underwater_light')
    if not fs: return None
    i = int(t * 24 * speed) % len(fs)
    return _caus_img(fs[i])


@functools.lru_cache(8)
def _caus_img(p):
    a = np.asarray(Image.open(p).convert('L').resize((W // 2, H // 2), Image.BILINEAR), np.float32)
    a = np.clip((a - 60) / 160, 0, 1) ** 1.6
    return np.asarray(Image.fromarray((a * 255).astype(np.uint8)).resize((W, H), Image.BILINEAR), np.float32) / 255


WTOP, WDEEP = np.array([40, 150, 210], np.float32), np.array([2, 9, 28], np.float32)


def water(x, surf, deep=420, a0=0.48, a1=0.94, tint=None, caus=0.22, foam=1.0):
    """surf：長 W 的海面 y；海面以下疊海水漸層＋光紋＋白浪線"""
    y0 = int(max(0, np.floor(surf.min()) - 3))
    if y0 >= H: return
    arr = np.asarray(x.img, np.float32)[y0:, :, :3].copy()
    D = YG[y0:] - surf[None, :]
    m = D > 0
    k_ = np.ones(401, np.float32) / 401
    s2 = np.convolve(np.pad(surf, 200, mode='edge'), k_, mode='valid')[:W]
    s2 = np.convolve(np.pad(s2, 200, mode='edge'), k_, mode='valid')[:W]
    q = np.clip((YG[y0:] - s2[None, :]) / deep, 0, 1)
    top = WTOP if tint is None else np.array(tint[0], np.float32)
    dp = WDEEP if tint is None else np.array(tint[1], np.float32)
    col = top[None, None] * (1 - q[..., None]) + dp[None, None] * q[..., None]
    a = np.where(m, a0 + (a1 - a0) * q, 0.0)[..., None]
    arr = arr * (1 - a) + col * a
    if caus:
        c = _caus(x.T if hasattr(x, 'T') else x.t)
        if c is not None:
            arr += (c[y0:, :, None] * np.array([150, 220, 255], np.float32)[None, None]) * (caus * m * (1 - q) ** 1.5)[..., None]
    if foam:
        fb = np.clip(1 - np.abs(D - 1.5) / 3.0, 0, 1) * foam
        arr = arr * (1 - fb[..., None]) + np.array([235, 250, 255], np.float32) * fb[..., None]
        gl = np.clip(1 - np.abs(D + 2) / 14, 0, 1) * 0.25 * foam  # 海面上緣的光暈
        arr += gl[..., None] * np.array([120, 210, 255], np.float32)
    out = np.asarray(x.img).copy()
    out[y0:, :, :3] = np.clip(arr, 0, 255).astype(np.uint8)
    x.img.paste(Image.fromarray(out, 'RGBA'))


def surface(pts, t, amp=5.0, smooth=31, right=None):
    """pts=[(x,y)] 依 x 排序 → 長 W 的海面（平滑＋波動）"""
    xs = np.array([p[0] for p in pts], np.float32); ys = np.array([p[1] for p in pts], np.float32)
    s = np.interp(XG, xs, ys)
    if smooth > 1:
        k = np.hanning(smooth); k /= k.sum(); pad = smooth // 2
        s = np.convolve(np.pad(s, pad, mode='edge'), k, mode='valid')[:W]
    s = s + amp * np.sin(XG * 0.021 + t * 2.3) + amp * 0.55 * np.sin(XG * 0.057 - t * 3.4)
    return s


def bubbles(x, surf, n=36, seed=5, op=1.0):
    rnd = random.Random(seed); d = ImageDraw.Draw(x.img)
    for i in range(n):
        bx = rnd.uniform(0, W); sp = rnd.uniform(40, 110); r = rnd.uniform(2, 7); ph = rnd.uniform(0, 1)
        yb = H + 20 - ((x.t * sp + ph * (H + 200)) % (H + 200))
        bx += 8 * math.sin(x.t * 2 + i)
        xi = int(min(max(bx, 0), W - 1))
        if yb < surf[xi] + 10: continue
        a = int(150 * op * min(1, (yb - surf[xi]) / 60))
        d.ellipse((bx - r, yb - r, bx + r, yb + r), outline=(200, 240, 255, a), width=2)


# ───────────── 小元件 ─────────────
def pin(d, xc, yc, s, col, age, up=True, fk='zhb', size=34, life=2.6, sub=None):
    """釘在 K 棒上的事件卡：細線＋色塊標籤"""
    if age < 0 or age > life: return
    a = min(1, age / 0.15) * min(1, (life - age) / 0.4)
    L = 70 + 30 * ease(min(1, age / 0.25), 'out')
    y1 = yc - L if up else yc + L
    d.line((xc, yc, xc, y1), fill=col + (int(220 * a),), width=3)
    d.ellipse((xc - 6, yc - 6, xc + 6, yc + 6), fill=col + (int(255 * a),))
    F = font(fk, size); tw = d.textlength(s, font=F)
    bx = min(max(xc - tw / 2 - 16, 20), W - tw - 52)
    by = y1 - size - 22 if up else y1
    d.rectangle((bx, by, bx + tw + 32, by + size + 22), fill=(6, 12, 30, int(225 * a)), outline=col + (int(255 * a),), width=3)
    d.text((bx + 16, by + 6), s, font=F, fill=WHITE + (int(255 * a),))
    if sub:
        F2 = font('num', int(size * 1.1)); d.text((bx + 16, by + size + 26), sub, font=F2, fill=col + (int(255 * a),))


def hud(d, name, date, v, chg, dec=0, col=CYAN, x0=64, y0=44):
    d.rectangle((x0 - 24, y0 - 14, x0 + 560, y0 + 196), fill=(4, 10, 26, 150))
    d.rectangle((x0 - 24, y0 - 14, x0 - 16, y0 + 196), fill=col + (255,))
    d.text((x0, y0), name, font=font('zh', 44), fill=WHITE + (255,))
    tw = d.textlength(name, font=font('zh', 44))
    d.text((x0 + tw + 20, y0 + 6), date, font=font('num', 46), fill=(180, 200, 235, 255))
    s = fmt(v, dec); d.text((x0, y0 + 62), s, font=font('num', 112), fill=WHITE + (255,))
    tw = d.textlength(s, font=font('num', 112))
    c2 = UP if chg >= 0 else DN; s2 = f'{chg:+.2f}%'
    d.text((x0 + tw + 22, y0 + 112), s2, font=font('num', 56), fill=c2 + (255,))


def _rider(x, p, xc, yfeet, h, age, flip=False, h0=0.46):
    hp = int(h0 * H); spr, pad = _spr(C2(p), hp, OLR, None, flip)
    sc = h / h0
    if age < 0.22: sc *= 0.86 + 0.14 * ease(age / 0.22, 'back')
    im2 = spr if abs(sc - 1) < 1e-3 else spr.resize((int(spr.width * sc), int(spr.height * sc)), Image.BILINEAR)
    pd = pad * sc
    eng._safe_comp(x.img, im2, (xc - im2.width / 2, yfeet - (im2.height - pd)))


def splash(x, xc, yc, t, age=9.0, k=1.0):
    """腳邊白浪：常駐的小水花＋換姿勢時的大水花"""
    lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    rnd = random.Random(int(t * 24) // 3)
    for i in range(10):
        dx = rnd.uniform(-150, 150); r = rnd.uniform(4, 12)
        d.ellipse((xc + dx - r, yc - r * 0.5 - rnd.uniform(0, 14), xc + dx + r, yc + r * 0.5), fill=(240, 250, 255, 150))
    if age < 0.9:
        q = age / 0.9; r2 = random.Random(7)
        for i in range(46):
            ang = r2.uniform(math.pi * 1.05, math.pi * 1.95); sp = r2.uniform(300, 900) * k
            px = xc + math.cos(ang) * sp * q; py = yc + math.sin(ang) * sp * q + 1300 * q * q
            rr = r2.uniform(4, 11) * (1 - q * 0.5)
            d.ellipse((px - rr, py - rr, px + rr, py + rr), fill=(235, 248, 255, int(230 * (1 - q))))
        R_ = 60 + 260 * ease(q, 'out')
        d.ellipse((xc - R_, yc - R_ * 0.18, xc + R_, yc + R_ * 0.18), outline=(235, 250, 255, int(220 * (1 - q))), width=5)
    x.img.alpha_composite(lay)


# ───────────── 2026 日 K 海面 ─────────────
def sea(sym, d0, d1, beats, pre=0, sky=((0, 'sky_dawn'),), hx=0.60, slot=48, cw=0.58, top=250, bot=740, grow=0.2,
        rider=None, rider_h=0.46, rider_dx=210, events=(), title=None, dec=0, ref=None, prevhigh=True, month=True,
        dark=0.28, tint=None, glow=0.9, show_hud=True, ylim=None, hl=None, sky_dy=0.0, wamp=5.0, cam_lag=0.0):
    """beats＝鏡內秒，第 j 根（pre 之後）在 beats[j] 長完；
    rider=[(t, 'P012-above'[, flip])] 只在事件點換；events=[(date, kind, dict)]，kind：pin／high／crash"""
    rows = series(sym, d0, d1); n = len(rows)
    Bt = sorted(beats)[:max(0, n - pre)]
    if ref is not None: ref_ = ref
    else:
        pr = [r for r in OHLC[sym] if r[0] < '2026-01-01']
        ref_ = pr[-1][4] if pr else OHLC[sym][0][1]
    hi_run = np.maximum.accumulate([r[2] for r in rows])
    idx = {r[0]: i for i, r in enumerate(rows)}

    def tc(i):
        j = i - pre
        if j < 0: return -99.0
        return Bt[j] if j < len(Bt) else 1e9

    def prog(t):
        j = bisect.bisect_right(Bt, t); p = pre + j
        if j < len(Bt):
            st = Bt[j] - grow
            if t > st: p += (t - st) / grow
        return min(float(p), float(n))

    def price(k, fr):
        _, o, h, l, c = rows[k]
        if fr >= 1: return c, h, l
        g = ease(fr, 'out'); path = [o, l, h, c] if c >= o else [o, h, l, c]
        seen = [eng._seg(g * j / 10, path) for j in range(11)]
        return eng._seg(g, path), max(seen + [o]), min(seen + [o])

    nvis = int(hx * W / slot) + 2

    def lim(k):
        a = max(0, k - nvis); sub = rows[a:k + 1] or rows[:1]
        lo = min(r[3] for r in sub); hi = max(r[2] for r in sub); r_ = (hi - lo) or hi * 0.01
        return lo - r_ * 0.06, hi + r_ * 0.10

    def f(x):
        t = x.t
        p = prog(t); k = min(int(p), n - 1); fr = (p - int(p)) if p < n else 1.0
        if p < 1e-6: k, fr = 0, 0.0
        pcam = k + ease(min(1, fr), 'io') if p < n else float(n)
        if ylim: lo, hi = ylim
        else:
            la, lb = lim(max(k - 1, 0)), lim(k); g_ = ease(min(1, fr), 'io')
            lo, hi = lerp(la[0], lb[0], g_), lerp(la[1], lb[1], g_)
        cur, chh, cll = price(k, fr) if p > 0 else (rows[0][1], rows[0][1], rows[0][1])
        lo = min(lo, cll); hi = max(hi, chh)
        X = lambda i: hx * W - (pcam - i - 0.5) * slot
        Y = lambda v: bot - (v - lo) / (hi - lo) * (bot - top)
        # 天空：隨相機微微平移；閃電時亮一下
        fl = 0.0
        for dt_, kind, kw in events:
            if kind == 'crash' and dt_ in idx:
                q = t - tc(idx[dt_]) + 0.05
                if 0 <= q < 0.12: fl = 0.55
        sky_paint(x, sky, shift=-pcam * 3.0, dark=dark, flash=fl, dy=sky_dy)
        d = ImageDraw.Draw(x.img)
        # 格線
        for gi in range(5):
            gv = lo + (hi - lo) * (gi + 0.5) / 5; gy = Y(gv)
            for xx in range(0, W, 18): d.line((xx, gy, xx + 8, gy), fill=(170, 200, 240, 34), width=1)
            d.text((W - 150, gy - 30), fmt(gv, dec), font=font('mono', 22), fill=(190, 210, 240, 120))
        i0 = max(0, int(pcam - nvis) - 1)
        # 月份分隔
        if month:
            for i in range(max(1, i0), k + 1):
                if rows[i][0][5:7] != rows[i - 1][0][5:7]:
                    xm = X(i) - slot / 2
                    d.line((xm, top - 70, xm, bot + 40), fill=(200, 220, 255, 40), width=1)
                    d.text((xm + 8, top - 78), f'{int(rows[i][0][5:7])}月', font=font('zhb', 26), fill=(210, 225, 255, 150))
        # 前高
        if prevhigh and k >= 1:
            ph = hi_run[k - 1]
            if lo < ph < hi:
                gy = Y(ph)
                for xx in range(0, int(X(k) + slot), 22): d.line((xx, gy, xx + 11, gy), fill=GOLD + (150,), width=2)
                d.text((24, gy - 34), f'前高 {fmt(ph, dec)}', font=font('zhb', 24), fill=GOLD + (200,))
        # K 棒
        lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
        bw = slot * cw
        for i in range(i0, k + 1):
            xc = X(i)
            if xc < -slot or xc > W + slot: continue
            if i == k and p < n:
                o = rows[i][1]; cc, hh, ll = cur, chh, cll
                if fr <= 0: continue
            else: _, o, hh, ll, cc = rows[i]
            col = UP if cc >= o else DN
            if hl and rows[i][0] in hl: col = hl[rows[i][0]]
            dl.line((xc, Y(hh), xc, Y(ll)), fill=col + (255,), width=4)
            ya, yb = sorted((Y(o), Y(cc)))
            dl.rectangle((xc - bw / 2, ya, xc + bw / 2, max(yb, ya + 4)), fill=col + (255,))
            dl.rectangle((xc - bw / 2, ya, xc + bw / 2, max(yb, ya + 4)), outline=(255, 255, 255, 70), width=1)
        # 海面：收盤連線，線頭往右平鋪
        pts = [(X(i), Y(rows[i][4] if not (i == k and p < n) else cur)) for i in range(i0, k + 1)]
        if not pts: pts = [(0, Y(cur))]
        hxp, hyp = pts[-1]
        pts = [(min(pts[0][0], 0) - 10, pts[0][1])] + pts + [(max(W, hxp) + 10, hyp)]
        surf = surface(pts, x.T if hasattr(x, 'T') else t, amp=wamp)
        # DS 娘（在海水之前畫，腳泡在水裡）
        if rider:
            cur_r = None; t_r = -9
            for r in rider:
                if t >= r[0]: cur_r, t_r = r, r[0]
            if cur_r:
                h_ = rider_h * (cur_r[3] if len(cur_r) > 3 else 1.0)
                xr = min(hxp + rider_dx, W - 0.14 * W)
                sxr = int(min(max(xr, 0), W - 1))
                ys_ = surf[sxr]; h_ = min(h_, max(0.24, (ys_ - 24) / (0.92 * H)))
                yf = ys_ + 0.08 * h_ * H + 6 * math.sin(t * 2.4)
                _rider(x, cur_r[1], xr, yf, h_, t - t_r, flip=cur_r[2] if len(cur_r) > 2 else False, h0=rider_h)
        water(x, surf, tint=tint)
        bubbles(x, surf, 30, 3)
        if glow:
            gl = lay.resize((W // 4, H // 4), Image.BILINEAR).filter(ImageFilter.GaussianBlur(4)).resize((W, H), Image.BILINEAR)
            add_light(x.img, gl, glow)
        x.img.alpha_composite(lay)
        if rider and cur_r: splash(x, xr, surf[sxr] + 4, t, t - t_r if t_r > 0.01 else 9.0)
        d = ImageDraw.Draw(x.img)
        # 線頭價位
        cc = UP if cur >= (rows[k - 1][4] if k else rows[0][1]) else DN
        s = fmt(cur, dec); F = font('num', 44); tw = d.textlength(s, font=F)
        yy = Y(cur); bx = min(hxp + 26, W - tw - 40)
        d.rectangle((bx, yy - 26, bx + tw + 22, yy + 24), fill=cc + (240,)); d.text((bx + 11, yy - 25), s, font=F, fill=WHITE + (255,))
        # 事件
        _st = sorted(tc(idx[e[0]]) for e in events if e[0] in idx and e[1] in ('pct', 'crash'))
        for dt_, kind, kw in events:
            if dt_ not in idx: continue
            i = idx[dt_]; age = t - tc(i)
            if kind == 'pct':
                nx = [s_ for s_ in _st if s_ > tc(i) + 0.05]
                if nx and t >= nx[0]: continue
            if age < -0.1 or age > kw.get('life', 3.0) or i > k: continue
            xc = X(i); r_ = rows[i]
            if kind == 'pin':
                up = kw.get('up', True)
                pin(d, xc, Y(r_[2]) - 10 if up else Y(r_[3]) + 10, kw['s'], kw.get('col', CYAN), age, up=up, life=kw.get('life', 2.6), sub=kw.get('sub'))
            elif kind == 'pct' and age >= 0:
                ch = 100 * (r_[4] / rows[i - 1][4] - 1) if i else 0
                up = ch >= 0; colb = UP if up else DN; sz = kw.get('size', 120)
                sc_ = ease(min(1, max(age, 0) / 0.25), 'back'); F = font('num', max(8, int(sz * sc_)))
                s2 = f'{ch:+.2f}%'; tw = d.textlength(s2, font=F)
                by = (Y(r_[2]) - sz - 40) if up else (Y(r_[3]) + 30)
                by = min(max(by, 150), H - sz - 160); bx = min(max(xc - tw / 2, 30), W - tw - 60)
                a = int(245 * min(1, (kw.get('life', 3.0) - age) / 0.4))
                d.rectangle((bx - 16, by + 8, bx + tw + 16, by + sz * sc_ + 4), fill=colb + (a,))
                d.text((bx, by), s2, font=F, fill=WHITE + (a,))
        f._geo = (X, Y, k)
        for fn in f._fx: fn(x)
        if show_hud:
            nm = title or NAME.get(sym, sym)
            hud(d, nm, rows[k][0][5:].replace('-', '.'), cur, 100 * (cur / ref_ - 1), dec,
                col=GOLD if sym in ('GC_F', 'BTC-USD') else CYAN)

    # 事件特效（閃電、煙火、碎字）：用 f._geo 取當格座標
    f._fx = []
    for dt_, kind, kw in events:
        if dt_ not in idx: continue
        i = idx[dt_]; t0 = tc(i)
        if kind == 'crash':
            def pe(tt, i=i):
                X, Y, k = f._geo; return (X(i), Y(rows[i][3]))
            f._fx.append(lightning(t0 - 0.05, pe, seed=i + 3, dur=0.6))
            if kw.get('big'):
                f._fx.append(shatter(kw['big'], kw.get('xy', (0.42, 0.42)), kw.get('size', 250), DN, t_in=t0 + 0.02, t_break=t0 + kw.get('hold', 1.2), seed=i))
        elif kind == 'high':
            f._fx.append(ovl_vid(kw.get('vid', 'fireworks_black'), op=kw.get('op', 0.85), t0=t0, t1=t0 + kw.get('life', 2.8), start=0.0))
            if kw.get('big'):
                f._fx.append(slam(kw['big'], kw.get('xy', (0.40, 0.36)), kw.get('size', 220), GOLD, t_in=t0, t_out=t0 + kw.get('life', 2.8)))
    f.n, f.rows, f.tc, f.idx = n, rows, tc, idx
    return f


def chars_in(C, a, b, skip=()):
    """chars.json 中 [a,b) 的字時間（去掉幻覺字串）"""
    return [t for t, ch in C if a <= t < b and ch not in skip and '\u4e00' <= ch <= '\u9fff']


# ───────────── 數十年海面 ─────────────
def longsea(sym, since=None, keys=((0, None, None, 2026.9),), log=True, sky=((0, 'sky_night'),), dark=0.3, eras=(),
            title=None, dec=0, top=330, bot=770, rider=None, rider_h=0.30, show_hud=True, hl26=True, tint=None, mark=None):
    """keys=[(t, 左年, 右年, 畫到哪一年)]：鏡內秒的關鍵格，之間 ease；左右年 None＝全歷史。
    eras=[(年, '文字', 色[, up])]：線畫過該年時把事件釘在浪上"""
    D = long_rows(sym, since); Xs = np.array([d[0] for d in D]); V = np.array([d[1] for d in D], float)
    Vl = np.log(V) if log else V
    xa, xb = Xs[0], Xs[-1]

    def key(t):
        ks = list(keys)
        if t <= ks[0][0]: a = b = ks[0]; u = 0
        elif t >= ks[-1][0]: a = b = ks[-1]; u = 0
        else:
            j = max(i for i, k in enumerate(ks) if k[0] <= t); a, b = ks[j], ks[j + 1]; u = ease((t - a[0]) / (b[0] - a[0]), 'io')
        L = lerp(a[1] if a[1] is not None else xa, b[1] if b[1] is not None else xa, u)
        Rr = lerp(a[2] if a[2] is not None else xb, b[2] if b[2] is not None else xb, u)
        un = lerp(a[3], b[3], u)
        return L, Rr, un

    def fit(t):
        L, Rr, un = key(t); m = (Xs >= L - 0.2) & (Xs <= min(Rr, un) + 0.05)
        if m.sum() < 2: m = Xs <= Xs[1]
        lo, hi = Vl[m].min(), Vl[m].max(); r = (hi - lo) or 0.1
        return lo - r * 0.08, hi + r * 0.14

    def f(x):
        t = x.t; L, Rr, un = key(t)
        fs = [fit(t - 0.1 * j) for j in range(5)]
        lo = sum(a for a, _ in fs) / 5; hi = sum(b for _, b in fs) / 5
        Xp = lambda yr: (yr - L) / (Rr - L) * W * 0.80 + W * 0.04
        Yp = lambda v: bot - (v - lo) / (hi - lo) * (bot - top)
        sky_paint(x, sky, shift=-(L - xa) * 4, dark=dark)
        d = ImageDraw.Draw(x.img)
        # 年份格
        step = 1 if Rr - L < 8 else (2 if Rr - L < 16 else 5)
        for yr in range(int(L) - 1, int(Rr) + 2):
            if yr % step: continue
            xx = Xp(yr)
            if 0 <= xx <= W:
                d.line((xx, top - 60, xx, bot + 60), fill=(200, 220, 255, 30), width=1)
                d.text((xx + 6, top - 70), str(yr), font=font('num', 34), fill=(210, 225, 255, 140))
        m = Xs <= un
        if m.sum() < 2: return
        xs = Xp(Xs[m]); ys = Yp(Vl[m])
        # 線頭插值
        j = int(m.sum()) - 1
        if j + 1 < len(Xs):
            u = (un - Xs[j]) / max(Xs[j + 1] - Xs[j], 1e-6)
            xs = np.append(xs, Xp(un)); ys = np.append(ys, Yp(lerp(Vl[j], Vl[j + 1], min(max(u, 0), 1))))
        lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
        sel = (xs > -40) & (xs < W + 40)
        P = list(zip(xs[sel].tolist(), ys[sel].tolist()))
        if len(P) > 1: dl.line(P, fill=(190, 225, 255, 255), width=4, joint='curve')
        if hl26:
            s26 = (Xs[m] >= 2026) if True else None
            P2 = [(a, b) for a, b, yy in zip(xs.tolist(), ys.tolist(), list(Xs[m]) + [un]) if yy >= 2025.99]
            if len(P2) > 1: dl.line(P2, fill=UP + (255,), width=7, joint='curve')
        gl = lay.resize((W // 4, H // 4), Image.BILINEAR).filter(ImageFilter.GaussianBlur(5)).resize((W, H), Image.BILINEAR)
        add_light(x.img, gl, 1.3); x.img.alpha_composite(lay)
        hx_, hy_ = float(xs[-1]), float(ys[-1])
        pts = [(-10, float(ys[0]) if xs[0] > 0 else float(np.interp(0, xs, ys)))] + list(zip(xs.tolist(), ys.tolist())) + [(W + 10, hy_)]
        pts = [p for p in pts if -60 <= p[0] <= W + 60] or [(0, hy_), (W, hy_)]
        if pts[0][0] > 0: pts = [(0, pts[0][1])] + pts
        if pts[-1][0] < W: pts = pts + [(W, pts[-1][1])]
        surf = surface(pts, x.T if hasattr(x, 'T') else t, amp=4, smooth=9)
        if rider:
            cur_r = None; t_r = -9
            for r in rider:
                if t >= r[0]: cur_r, t_r = r, r[0]
            if cur_r:
                xr = min(hx_ + 120, W - 140); sxr = int(min(max(xr, 0), W - 1))
                ys_ = surf[sxr]; h_ = min(rider_h, max(0.2, (ys_ - 24) / (0.92 * H)))
                yf = ys_ + 0.08 * h_ * H + 5 * math.sin(t * 2.4)
                _rider(x, cur_r[1], xr, yf, h_, t - t_r, flip=cur_r[2] if len(cur_r) > 2 else False, h0=rider_h)
        water(x, surf, tint=tint, deep=360)
        bubbles(x, surf, 26, 9)
        d = ImageDraw.Draw(x.img)
        # 線頭亮點
        r = 10 + 3 * math.sin(t * 8)
        d.ellipse((hx_ - r, hy_ - r, hx_ + r, hy_ + r), fill=WHITE + (255,))
        # 事件釘
        for e_ in eras:
            yr, s, col = e_[:3]; up = e_[3] if len(e_) > 3 else False
            if un < yr: continue
            age = (un - yr) / max((Rr - L) / 8, 0.3)  # 依推進速度換算「年齡」
            jj = int(np.argmin(np.abs(Xs - yr)))
            pin(d, Xp(Xs[jj]), Yp(Vl[jj]) + (-10 if up else 10), s, col, age * 1.2, up=up, life=3.6, size=32)
        if show_hud:
            vv = float(np.exp(lerp(Vl[j], Vl[min(j + 1, len(Vl) - 1)], 0)) if log else V[j])
            yr_ = int(min(un, Xs[-1])); mo = int(((min(un, Xs[-1]) - yr_) * 12)) + 1
            hud(d, title or NAME.get(sym, sym), f'{yr_}.{mo:02d}', V[j], 100 * (V[j] / V[0] - 1), dec)
        if mark: mark(x, Xp, Yp)
    f.rows = D
    return f
