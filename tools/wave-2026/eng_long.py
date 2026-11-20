"""長期線圖：Yahoo 月線（數十年）＋2026 日線，2026 段高亮；鏡頭可從 2026 拉遠到全歷史"""
import datetime as _dt
from eng import *  # noqa
import eng

_LONG = json.load(open(R + '/30_data/long.json'))


def long_rows(sym, since=None):
    out = []
    for d, v in _LONG.get(sym, []):
        y, m = int(d[:4]), int(d[5:7])
        if y >= 2026 or (since and y < since): continue
        out.append((y + m / 12, v))
    for r in OHLC.get(sym, []):
        dd = _dt.date.fromisoformat(r[0])
        if dd.year < 2026: continue
        out.append((2026 + (dd.timetuple().tm_yday - 0.5) / 365, r[4]))
    return out


def _nice_years(w):
    for s in (0.25, 0.5, 1, 2, 5, 10):
        if w / s <= 11: return s
    return 10


def longline(sym, since=None, rev=None, zk=None, log=False, box=(110, 190, 1700, 900), col=(150, 180, 230), hl=UP,
             events=(), title=None, sub=None, dec=0, glow=1.0, e='io', head=True, band=True, t_in=0.0, until=None):
    """rev=(u0,u1)：線從最早畫到最新；None＝一開始就畫好。
    zk=[(u, xa, xb)]：鏡頭視窗關鍵格（年份小數，None＝資料頭／尾），寬度在對數空間內插，看起來是等速拉遠。
    events=[(年份小數, 文字, 顏色)]：畫到、且在視窗內才出現。"""
    P = long_rows(sym, since)
    if until: P = [p for p in P if p[0] <= until]
    xs = [p[0] for p in P]; vs = [p[1] for p in P]
    tmin, tmax = xs[0], xs[-1]
    T = (lambda v: math.log10(max(v, 1e-9))) if log else (lambda v: v)
    Ti = (lambda q: 10 ** q) if log else (lambda q: q)
    K = [(u, tmin if a is None else a, tmax if b is None else b) for u, a, b in (zk or [(0, None, None)])]
    x0, y0, x1, y1 = box

    def win(u):
        if u <= K[0][0]: return K[0][1], K[0][2]
        for (ua, aa, ab), (ub, ba, bb) in zip(K, K[1:]):
            if u <= ub:
                g = ease((u - ua) / max(ub - ua, 1e-6), 'io')
                wa, wb = ab - aa, bb - ba
                w_ = math.exp(lerp(math.log(wa), math.log(wb), g)); xr = lerp(ab, bb, g)
                return xr - w_, xr
        return K[-1][1], K[-1][2]

    def f(x):
        if x.t < t_in: return
        u = x.u
        if rev: td = tmin + (tmax - tmin) * ease(min(1, max(0, (u - rev[0]) / max(rev[1] - rev[0], 1e-6))), e)
        else: td = tmax
        xa, xb = win(u)
        idx = [i for i in range(len(xs)) if xs[i] <= td]
        if not idx: return
        vis = [i for i in idx if xa <= xs[i] <= xb] or idx[-1:]
        lo = min(T(vs[i]) for i in vis); hi = max(T(vs[i]) for i in vis); r_ = (hi - lo) or abs(hi) * 0.02 or 1
        lo -= r_ * 0.08; hi += r_ * 0.20
        if not log and lo < 0 <= min(T(vs[i]) for i in vis): lo = 0
        X = lambda t: x0 + (t - xa) / (xb - xa) * (x1 - x0)
        Y = lambda v: y1 - (T(v) - lo) / (hi - lo) * (y1 - y0)
        lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
        # 網格
        for gi in range(6):
            q = lo + (hi - lo) * gi / 5; gy = y1 - (q - lo) / (hi - lo) * (y1 - y0)
            d.line((x0, gy, x1, gy), fill=(110, 140, 200, 36), width=1)
            d.text((x1 + 14, gy - 14), fmt(Ti(q), dec), font=font('mono', 22), fill=(150, 175, 220, 120))
        st = _nice_years(xb - xa); yy = math.ceil(xa / st) * st
        while yy <= xb:
            gx = X(yy)
            d.line((gx, y1, gx, y1 + 12), fill=(150, 175, 220, 160), width=2)
            lab = f'{int(yy)}' if st >= 1 else f'{int(yy)}.{int(round((yy % 1) * 12)) + 1:02d}'
            d.text((gx, y1 + 18), lab, font=font('mono', 24), fill=(170, 190, 230, 200), anchor='ma')
            yy += st
        # 2026 帶狀底
        if band and td >= 2026 and xb > 2026:
            bx = max(X(2026.0), x0)
            d.rectangle((bx, y0 - 10, min(X(td), x1), y1), fill=hl + (26,))
            if min(X(td), x1) - bx > 110 and not any(v[0] >= 2026 for v in events): d.text((bx + 10, y0 - 4), '2026', font=font('num', 40), fill=hl + (220,))
        # 線
        lo_i = max(0, (vis[0] - 1)); hi_i = idx[-1]
        pts = [(X(xs[i]), Y(vs[i])) for i in range(lo_i, hi_i + 1)]
        old = [p for i, p in zip(range(lo_i, hi_i + 1), pts) if xs[i] <= 2026.0]
        new = [p for i, p in zip(range(lo_i, hi_i + 1), pts) if xs[i] >= 2026.0 - 1 / 12]
        ln = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ln)
        if len(old) > 1:
            d.polygon(old + [(old[-1][0], y1), (old[0][0], y1)], fill=col + (30,))
            d.line(old, fill=col + (235,), width=4, joint='curve')
        if len(new) > 1:
            d.polygon(new + [(new[-1][0], y1), (new[0][0], y1)], fill=hl + (60,))
            d.line(new, fill=hl + (255,), width=7, joint='curve')
        mk = Image.new('L', (W, H), 0); ImageDraw.Draw(mk).rectangle((x0, 0, x1 + 3, H), fill=255)
        ln.putalpha(ImageChops.multiply(ln.getchannel('A'), mk)); lay.alpha_composite(ln)
        if glow:
            gl = lay.resize((W // 4, H // 4), Image.BILINEAR).filter(ImageFilter.GaussianBlur(5)).resize((W, H), Image.BILINEAR)
            add_light(x.img, gl, glow)
        x.img.alpha_composite(lay)
        d2 = ImageDraw.Draw(x.img)
        # 事件標籤
        for et, s, ec in events:
            if et > td or not xa <= et <= xb: continue
            j = min(range(len(xs)), key=lambda i: abs(xs[i] - et)); ex, ey = X(xs[j]), Y(vs[j])
            F = font('zhb', 34); tw = d2.textlength(s, font=F)
            ty = max(y0 + 10, ey - 120)
            for yy_ in range(int(ty + 46), int(ey - 10), 14): d2.line((ex, yy_, ex, yy_ + 7), fill=ec + (200,), width=2)
            bx = min(max(ex - tw / 2, x0), x1 - tw)
            d2.rectangle((bx - 12, ty, bx + tw + 12, ty + 46), fill=(6, 10, 24, 220), outline=ec + (255,), width=2)
            d2.text((bx, ty + 4), s, font=F, fill=ec + (255,))
            d2.ellipse((ex - 8, ey - 8, ex + 8, ey + 8), fill=ec + (255,))
        if head:
            hx, hy = pts[-1]; cv = vs[hi_i]
            pr = 10 + 6 * abs(math.sin(x.T * 6))
            d2.ellipse((hx - pr, hy - pr, hx + pr, hy + pr), outline=hl + (200,), width=3)
            d2.ellipse((hx - 8, hy - 8, hx + 8, hy + 8), fill=WHITE + (255,))
            s = fmt(cv, dec); F = font('num', 48); tw = d2.textlength(s, font=F)
            tx = min(hx + 22, x1 + 150 - tw)
            d2.rectangle((tx - 8, hy - 30, tx + tw + 10, hy + 26), fill=hl + (255,))
            d2.text((tx, hy - 28), s, font=F, fill=(8, 10, 20, 255))
        if title:
            d2.text((x0, y0 - 120), title, font=font('zh', 60), fill=WHITE + (255,))
            tw = d2.textlength(title, font=font('zh', 60))
            d2.text((x0 + tw + 28, y0 - 104), sub or f'{int(xa)}–{int(min(td, xb))}', font=font('num', 56), fill=(170, 195, 235, 230))
    return f
