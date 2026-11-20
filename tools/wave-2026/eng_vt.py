"""VT 版行情（v5）
- 圖表放大：一畫面約 10 根日 K，單根大而清楚；K 棒從開盤長到收盤，不畫穿過 K 棒的收盤線。
- DS 娘固定在右側當 VTuber（大半身，下半身泡在底部海浪裡），跟著拍點輕彈；
  rider 排程換動作，大 K 棒自動換反應動作（最短停留 hold 秒，不連閃）。
- 長 K 特效：長的過程有拖光與加強光暈；收完時衝擊環、火花、白閃、大百分比。
- 海只當舞台：底部浪帶＋模糊天空當氛圍，不再填在線下。"""
from eng_sea import *  # noqa
import eng_sea as ES
import eng

OFF0, BT0 = 0.099, 60 / 148
POSE_HEAD = {'P011-above': 0.20}   # 舉手高過頭的動作：頭頂在圖高的比例


# ───────────── 背景（模糊天空）＋圖表暗底＋DS 背光 ─────────────
@functools.lru_cache(16)
def _skyblur(name, dark):
    im = ES._sky(name)
    sm = im.resize((im.width // 3, im.height // 3), Image.BILINEAR).filter(ImageFilter.GaussianBlur(1.6)).resize(im.size, Image.BILINEAR)
    return Image.blend(sm, Image.new('RGB', sm.size, (2, 6, 18)), dark)


def _bg(x, keys, shift, dark, flash):
    def crop(nm):
        im = _skyblur(nm, round(dark, 2)); mx, my = im.width - W, im.height - H
        x0 = int(min(max(mx / 2 + shift, 0), mx)); y0 = int(my / 2)
        return im.crop((x0, y0, x0 + W, y0 + H))
    cur = keys[0][1]; prev = None; u = 1.0
    for t0, nm in keys:
        if x.t >= t0: prev, cur = cur, nm; u = min(1.0, (x.t - t0) / 0.6)
    im = crop(cur)
    if prev and prev != cur and u < 1: im = Image.blend(crop(prev), im, ease(u, 'io'))
    if flash > 0: im = Image.blend(im, Image.new('RGB', (W, H), (225, 240, 255)), min(0.8, flash))
    x.img.paste(im.convert('RGBA'))


@functools.lru_cache(4)
def _panel(cx, dsx):
    a = np.clip((cx * W + 160 - XG[None, :]) / 320, 0, 1) * np.ones((H, 1), np.float32) * 0.50
    lay = np.zeros((H, W, 4), np.uint8); lay[..., 0] = 3; lay[..., 1] = 8; lay[..., 2] = 24; lay[..., 3] = (a * 255).astype(np.uint8)
    r = np.sqrt(((XG[None, :] - dsx * W) / 560) ** 2 + ((YG - 0.40 * H) / 640) ** 2)
    g = np.clip(1 - r, 0, 1) ** 2
    gl = np.zeros((H, W, 4), np.uint8); gl[..., 0] = 40; gl[..., 1] = 130; gl[..., 2] = 230; gl[..., 3] = (g * 255 * 0.6).astype(np.uint8)
    return Image.fromarray(lay, 'RGBA'), Image.fromarray(gl, 'RGBA')


@functools.lru_cache(4)
def _lfade(x0, x1):
    """K 棒層左緣淡出"""
    return np.clip((XG - x0) / (x1 - x0), 0, 1)[None, :]


# ───────────── DS 娘（VT） ─────────────
RING = (40, 150, 255)
_vspr = functools.lru_cache(96)(eng._sprite)


def _vt(x, pose, flip, age, T, cx, head=0.07, hf=1.45, ring=RING):
    im0 = img(C2(pose)); hp = int(min(hf * H, 860 * im0.height / im0.width))
    spr, pad = _vspr(C2(pose), hp, (((255, 255, 255), 16), (ring, 10), ((8, 22, 60), 3)), None, flip)
    ph = ((T - OFF0) / BT0) % 1.0
    dy = 9 * (1 - ph) ** 4 + 4 * math.sin(T * 1.7)
    sc = 1.0
    if age < 0.26: sc = 0.88 + 0.12 * ease(age / 0.26, 'back')
    im2 = spr if sc == 1.0 else spr.resize((int(spr.width * sc), int(spr.height * sc)), Image.BILINEAR)
    ytop0 = head * H - POSE_HEAD.get(pose, 0.0) * hp - pad
    ya = 0.78 * H
    ytop = ya + (ytop0 - ya) * sc + dy
    eng._safe_comp(x.img, im2, (cx * W - im2.width / 2, ytop))


# ───────────── 長 K 特效 ─────────────
def _sparks(d, xc, yc, a, up, col, seed, n=30):
    r = random.Random(seed)
    for j in range(n):
        ang = r.uniform(-math.pi * 0.85, -math.pi * 0.15) if up else r.uniform(math.pi * 0.15, math.pi * 0.85)
        sp = r.uniform(420, 1250); life = r.uniform(0.45, 0.9)
        if a > life: continue
        g = 1500 if up else 900
        px = xc + math.cos(ang) * sp * a; py = yc + math.sin(ang) * sp * a + 0.5 * g * a * a
        vx = math.cos(ang) * sp; vy = math.sin(ang) * sp + g * a
        L = 0.03
        al = int(255 * (1 - a / life))
        c2 = tuple(int(c * 0.5 + 255 * 0.5) for c in col) if j % 3 == 0 else col
        d.line((px - vx * L, py - vy * L, px, py), fill=c2 + (al,), width=r.choice((3, 4, 5)))


def vt(sym, d0, d1, beats, pre=0, sky=((0, 'sky_dawn'),), cx=0.55, hx=0.40, slot=112, cw=0.64, top=270, bot=868, grow=0.22,
       rider=None, pose_up=None, pose_dn=None, hold=1.6, thr=None, events=(), title=None, dec=0, ref=None, prevhigh=True, month=True,
       dark=0.55, glow=1.0, show_hud=True, ylim=None, hl=None, sea_y=0.865, dsx=0.825, ds_hf=1.45, wamp=5.0, label_big=True, **_):
    """beats＝鏡內秒，第 j 根（pre 之後）在 beats[j] 長完。
    rider=[(t, pose[, flip])]：DS 娘基本動作排程；pose_up/pose_dn：大紅 K／大綠 K 時自動換的動作。
    events=[(date, kind, dict)]，kind：pin／pct／crash／high"""
    rows = series(sym, d0, d1); n = len(rows)
    Bt = sorted(beats)[:max(0, n - pre)]
    if ref is not None: ref_ = ref
    else:
        pr = [r for r in OHLC[sym] if r[0] < '2026-01-01']
        ref_ = pr[-1][4] if pr else OHLC[sym][0][1]
    hi_run = np.maximum.accumulate([r[2] for r in rows])
    idx = {r[0]: i for i, r in enumerate(rows)}
    chg = [0.0] + [100 * (rows[i][4] / rows[i - 1][4] - 1) for i in range(1, n)]

    def tc(i):
        j = i - pre
        if j < 0: return -99.0
        return Bt[j] if j < len(Bt) else 1e9

    # 長 K：本鏡長出來的 K 棒裡，漲跌幅明顯大的
    shown = [i for i in range(pre, n) if tc(i) < 1e8]
    if thr is None:
        med = float(np.median([abs(chg[i]) for i in shown])) if shown else 1.0
        thr = max(1.6, 2.4 * med)
    bigs = [i for i in shown if abs(chg[i]) >= thr and i > 0]
    bigtxt = {idx[e[0]] for e in events if e[0] in idx and e[1] in ('crash', 'high') and e[2].get('big')}

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

    nvis = int(hx * W / slot) + 1

    def lim(k):
        a = max(0, k - nvis); sub = rows[a:k + 1] or rows[:1]
        lo = min(r[3] for r in sub); hi = max(r[2] for r in sub); r_ = (hi - lo) or hi * 0.01
        return lo - r_ * 0.08, hi + r_ * 0.12

    # DS 動作時間軸
    rider = rider or [(0, 'P039-above')]
    tl = [(r[0], 'b', r[1], r[2] if len(r) > 2 else False, 0) for r in rider]
    last_ov = -9
    for i in bigs:
        tb = tc(i); p_ = pose_up if chg[i] > 0 else pose_dn
        if p_ and tb - last_ov >= 1.0:
            tl.append((tb + 0.02, 'o', p_, False, tb + hold)); last_ov = tb
    tl.sort(key=lambda e: e[0])
    pts = sorted(set([e[0] for e in tl] + [e[4] for e in tl if e[1] == 'o']))

    def state(t):
        base = None; ov = None
        for te, k_, p_, fl, until in tl:
            if te > t: break
            if k_ == 'b': base = (p_, fl)
            else: ov = (p_, fl, until)
        if ov and t < ov[2]: return ov[:2]
        return base or (tl[0][2], tl[0][3])

    def pose_at(t):
        cur = state(t); tch = -9.0; prev = None
        for tp in pts:
            if tp > t: break
            s_ = state(tp)
            if s_ != prev: tch = tp if prev is not None else -9.0; prev = s_
        return cur, tch

    xr = cx * W - 150  # 右側價格軸

    def f(x):
        t = x.t; T = x.T if hasattr(x, 'T') else t
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
        fl = 0.0
        for dt_, kind, kw in events:
            if kind == 'crash' and dt_ in idx:
                q = t - tc(idx[dt_]) + 0.05
                if 0 <= q < 0.12: fl = 0.5
        _bg(x, sky, -pcam * 2.0, dark, fl)
        pnl, dsg = _panel(cx, dsx)
        x.img.alpha_composite(pnl); add_light(x.img, dsg, 0.55)
        d = ImageDraw.Draw(x.img)
        # 格線＋右側價格軸
        for gi in range(5):
            gv = lo + (hi - lo) * (gi + 0.5) / 5; gy = Y(gv)
            for xx in range(0, int(xr) - 10, 18): d.line((xx, gy, xx + 8, gy), fill=(170, 200, 240, 30), width=1)
            d.text((xr + 14, gy - 16), fmt(gv, dec), font=font('mono', 24), fill=(190, 210, 240, 130))
        d.line((xr, top - 40, xr, bot + 20), fill=(190, 210, 240, 60), width=2)
        i0 = max(0, int(pcam - nvis) - 1)
        if month:
            for i in range(max(1, i0), k + 1):
                if rows[i][0][5:7] != rows[i - 1][0][5:7]:
                    xm = X(i) - slot / 2
                    if 0 < xm < xr:
                        d.line((xm, top - 30, xm, bot + 20), fill=(200, 220, 255, 45), width=1)
                        d.text((xm + 8, bot + 0), f'{int(rows[i][0][5:7])}月', font=font('zhb', 28), fill=(210, 225, 255, 150))
        if prevhigh and k >= 1:
            ph = hi_run[k - 1]
            if lo < ph < hi:
                gy = Y(ph)
                for xx in range(0, int(xr), 22): d.line((xx, gy, xx + 11, gy), fill=GOLD + (160,), width=2)
                d.text((24, gy - 36), f'前高 {fmt(ph, dec)}', font=font('zhb', 26), fill=GOLD + (210,))
        # K 棒
        lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
        lay2 = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d2 = ImageDraw.Draw(lay2)  # 長 K 額外光
        bw = slot * cw
        for i in range(i0, k + 1):
            xc = X(i)
            if xc < -slot or xc > xr - bw / 2: continue
            growing = (i == k and p < n)
            if growing:
                o = rows[i][1]; cc, hh, ll = cur, chh, cll
                if fr <= 0: continue
            else: _, o, hh, ll, cc = rows[i]
            col = UP if cc >= o else DN
            if hl and rows[i][0] in hl: col = hl[rows[i][0]]
            ya, yb = sorted((Y(o), Y(cc))); yb = max(yb, ya + 5)
            dl.line((xc, Y(hh), xc, Y(ll)), fill=col + (255,), width=6)
            dl.rounded_rectangle((xc - bw / 2, ya, xc + bw / 2, yb), radius=5, fill=col + (255,))
            hc = tuple(int(c * 0.55 + 255 * 0.45) for c in col)
            dl.rounded_rectangle((xc - bw / 2 + 6, ya + 4, xc - bw / 2 + 6 + bw * 0.22, max(ya + 5, yb - 4)), radius=3, fill=hc + (150,))
            dl.rounded_rectangle((xc - bw / 2, ya, xc + bw / 2, yb), radius=5, outline=(255, 255, 255, 90), width=2)
            age = t - tc(i)
            if 0 <= age < 0.12:  # 收完白閃
                dl.rounded_rectangle((xc - bw / 2, ya, xc + bw / 2, yb), radius=5, fill=(255, 255, 255, int(150 * (1 - age / 0.12))))
            if i in bigs:
                up = chg[i] > 0
                if growing:  # 拖光：往運動反方向拉出光條
                    yt = Y(cc)
                    for s_ in range(5):
                        ox = (s_ - 2) * bw * 0.22; Lr = 160 + 70 * (2 - abs(s_ - 2))
                        y2 = yt + (Lr if up else -Lr)
                        d2.line((xc + ox, yt, xc + ox, y2), fill=col + (150,), width=4)
                    d2.rounded_rectangle((xc - bw / 2 - 10, ya - 10, xc + bw / 2 + 10, yb + 10), radius=10, fill=col + (200,))
                elif age < 1.2:
                    d2.rounded_rectangle((xc - bw / 2 - 8, ya - 8, xc + bw / 2 + 8, yb + 8), radius=10, fill=col + (int(220 * max(0.25, 1 - age / 1.2)),))
        # 左緣淡出
        A = np.asarray(lay).copy(); A[..., 3] = (A[..., 3] * _lfade(30, 220)).astype(np.uint8); lay = Image.fromarray(A, 'RGBA')
        if glow:
            gl = lay.resize((W // 4, H // 4), Image.BILINEAR).filter(ImageFilter.GaussianBlur(4)).resize((W, H), Image.BILINEAR)
            add_light(x.img, gl, glow * 0.8)
        gl2 = lay2.resize((W // 4, H // 4), Image.BILINEAR).filter(ImageFilter.GaussianBlur(6)).resize((W, H), Image.BILINEAR)
        add_light(x.img, gl2, 1.4)
        x.img.alpha_composite(lay)
        # 長 K 收完：衝擊環＋火花＋大百分比
        fxl = Image.new('RGBA', (W, H), (0, 0, 0, 0)); df = ImageDraw.Draw(fxl)
        nb = [tc(j) for j in bigs]
        for jj, i in enumerate(bigs):
            age = t - tc(i)
            if age < 0 or age > 1.8 or i > k: continue
            xc = X(i); up = chg[i] > 0; col = UP if up else DN; yc = Y(rows[i][4])
            if age < 0.55:
                q = age / 0.55; R_ = 40 + 300 * ease(q, 'out')
                df.ellipse((xc - R_, yc - R_ * 0.55, xc + R_, yc + R_ * 0.55), outline=(255, 255, 255, int(230 * (1 - q))), width=6)
                R2 = 20 + 190 * ease(q, 'out')
                df.ellipse((xc - R2, yc - R2 * 0.55, xc + R2, yc + R2 * 0.55), outline=col + (int(255 * (1 - q)),), width=8)
            if age < 0.95: _sparks(df, xc, yc, age, up, col, seed=i * 7 + 1)
            nxt = nb[jj + 1] if jj + 1 < len(nb) else 1e9
            if label_big and i not in bigtxt and t < nxt and age < 1.6:
                sz = 104; sc_ = ease(min(1, age / 0.22), 'back'); F = font('num', max(8, int(sz * sc_)))
                s2 = f'{chg[i]:+.2f}%'; tw = df.textlength(s2, font=F)
                by = (Y(rows[i][2]) - sz - 50) if up else (Y(rows[i][3]) + 40)
                by = min(max(by, top - 20), bot - sz); bx = min(max(xc - tw / 2, 40), xr - tw - 30)
                a = int(250 * min(1, (1.6 - age) / 0.3))
                df.rectangle((bx - 18, by + 8, bx + tw + 18, by + sz * sc_ + 6), fill=col + (a,))
                df.text((bx, by), s2, font=F, fill=WHITE + (a,))
        add_light(x.img, fxl.filter(ImageFilter.GaussianBlur(5)), 0.9)
        x.img.alpha_composite(fxl)
        d = ImageDraw.Draw(x.img)
        # 線頭價位：虛線拉到右側價格軸
        cc = UP if cur >= (rows[k - 1][4] if k else rows[0][1]) else DN
        yy = Y(cur); hxp = X(k) + bw / 2 + 6
        for xx in range(int(hxp), int(xr), 16): d.line((xx, yy, xx + 8, yy), fill=cc + (200,), width=2)
        s = fmt(cur, dec); F = font('num', 46); tw = d.textlength(s, font=F)
        d.rectangle((xr + 4, yy - 28, xr + 4 + tw + 26, yy + 26), fill=cc + (245,)); d.text((xr + 17, yy - 27), s, font=F, fill=WHITE + (255,))
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
                up = kw.get('up', True) and Y(r_[2]) - 170 > top
                ES.pin(d, min(xc, xr - 60), Y(r_[2]) - 10 if up else Y(r_[3]) + 10, kw['s'], kw.get('col', CYAN), age, up=up,
                       life=kw.get('life', 2.6), sub=kw.get('sub'), size=38)
            elif kind == 'pct' and age >= 0 and i not in bigs:
                up = chg[i] >= 0; colb = UP if up else DN; sz = kw.get('size', 104)
                sc_ = ease(min(1, max(age, 0) / 0.25), 'back'); F = font('num', max(8, int(sz * sc_)))
                s2 = f'{chg[i]:+.2f}%'; tw = d.textlength(s2, font=F)
                by = (Y(r_[2]) - sz - 50) if up else (Y(r_[3]) + 40)
                by = min(max(by, top - 20), bot - sz); bx = min(max(xc - tw / 2, 40), xr - tw - 30)
                a = int(245 * min(1, (kw.get('life', 3.0) - age) / 0.4))
                d.rectangle((bx - 16, by + 8, bx + tw + 16, by + sz * sc_ + 6), fill=colb + (a,))
                d.text((bx, by), s2, font=F, fill=WHITE + (a,))
        f._geo = (X, Y, k)
        for fn in f._fx: fn(x)
        # DS 娘＋底部海浪
        (pose, flp), tch = pose_at(t)
        ring = RING
        for i in bigs:
            if tc(i) <= t < tc(i) + hold: ring = UP if chg[i] > 0 else DN
        _vt(x, pose, flp, t - tch, T, dsx, hf=ds_hf, ring=ring)
        surf = np.full(W, sea_y * H, np.float32) + wamp * np.sin(XG * 0.012 + T * 1.9) + wamp * 0.6 * np.sin(XG * 0.035 - T * 2.7)
        ES.water(x, surf, deep=170, a0=0.50, a1=0.96, caus=0.30)
        ES.bubbles(x, surf, 22, 3)
        ES.splash(x, dsx * W, surf[int(dsx * W)] + 4, T, t - tch if tch > -1 else 9.0, k=0.8)
        if show_hud:
            d = ImageDraw.Draw(x.img)
            nm = title or NAME.get(sym, sym)
            ES.hud(d, nm, rows[k][0][5:].replace('-', '.'), cur, 100 * (cur / ref_ - 1), dec,
                   col=GOLD if sym in ('GC_F', 'BTC-USD') else CYAN)

    f._fx = []
    for dt_, kind, kw in events:
        if dt_ not in idx: continue
        i = idx[dt_]; t0 = tc(i)
        if kind == 'crash':
            def pe(tt, i=i):
                X, Y, k = f._geo; return (X(i), Y(rows[i][3]))
            f._fx.append(lightning(t0 - 0.05, pe, seed=i + 3, dur=0.6))
            if kw.get('big'):
                f._fx.append(shatter(kw['big'], kw.get('vxy', (0.26, 0.40)), kw.get('vsize', 200), DN, t_in=t0 + 0.02, t_break=t0 + kw.get('hold', 1.2), seed=i))
        elif kind == 'high':
            f._fx.append(ovl_vid(kw.get('vid', 'fireworks_black'), op=kw.get('op', 0.85), t0=t0, t1=t0 + kw.get('life', 2.8), start=0.0))
            if kw.get('big'):
                f._fx.append(slam(kw['big'], kw.get('vxy', (0.27, 0.36)), kw.get('vsize', 190), GOLD, t_in=t0, t_out=t0 + kw.get('life', 2.8)))
    f.n, f.rows, f.tc, f.idx = n, rows, tc, idx
    f.bigs = [(tc(i), chg[i]) for i in bigs]
    return f
