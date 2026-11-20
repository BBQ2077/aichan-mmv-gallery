"""stock-2026 渲染引擎：每鏡＝時長＋圖層清單；圖層是 f(ctx) 直接畫在 ctx.img（RGBA 1920x1080）。
圖層工廠：bg_solid／bg_grad／bg_vid／bg_img／chart／candles／race／char／txt／counter／parts／ovl_vid／stripes／panels／ticker／datestamp
全片事件（絕對秒）：flash／glitch／shake／punch／black。"""
import os, json, math, glob, functools, random
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops, ImageOps

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H, FPS = 1920, 1080, 24
UFONT = os.path.expanduser('~/AppData/Local/Microsoft/Windows/Fonts/')
FONTS = {'num': R + '/10_img/font/BebasNeue-Regular.ttf', 'osw': R + '/10_img/font/Oswald%5Bwght%5D.ttf',
         'mono': R + '/10_img/font/JetBrainsMono-Bold.ttf', 'zh': UFONT + 'NotoSansCJKtc-Black.otf',
         'zhb': UFONT + 'NotoSansCJKtc-Bold.otf', 'zhl': UFONT + 'NotoSansCJKtc-Light.otf'}
UP, DN, GOLD, CYAN, NAVY, WHITE = (255, 59, 78), (25, 230, 140), (255, 201, 74), (79, 216, 255), (5, 10, 26), (255, 255, 255)
OHLC = json.load(open(R + '/30_data/ohlc.json'))
NAME = {'TWII': '台股加權', 'SOX': '費城半導體', 'IXIC': '那斯達克', 'GSPC': '標普500', 'N225': '日經225', 'KS11': '韓國KOSPI',
        'GC_F': '黃金', 'BTC-USD': '比特幣', 'CL_F': '原油', 'NVDA': 'NVIDIA', '2330.TW': '台積電'}


@functools.lru_cache(256)
def font(k, size):
    f = ImageFont.truetype(FONTS.get(k, k), size)
    if k == 'osw':
        try: f.set_variation_by_name('Bold')
        except Exception: pass
    return f


@functools.lru_cache(64)
def img(p, maxw=4000):
    p = p if os.path.isabs(p) else R + '/' + p
    im = Image.open(p).convert('RGBA')
    if im.width > maxw: im = im.resize((maxw, round(im.height * maxw / im.width)), Image.LANCZOS)
    return im


def ease(u, k='io'):
    u = min(max(u, 0.0), 1.0)
    if k == 'lin': return u
    if k == 'out': return 1 - (1 - u) ** 3
    if k == 'in': return u ** 3
    if k == 'back': c = 1.70158; return 1 + (c + 1) * (u - 1) ** 3 + c * (u - 1) ** 2
    return 3 * u * u - 2 * u ** 3


def lerp(a, b, u): return a + (b - a) * u


def lerpt(a, b, u): return tuple(lerp(x, y, u) for x, y in zip(a, b))


class Ctx:
    def __init__(s, img, t, dur, T, shot):
        s.img, s.t, s.dur, s.T, s.shot = img, t, dur, T, shot
        s.u = t / dur if dur > 0 else 0


def over(base, top, xy=(0, 0), op=1.0):
    if op < 1: top = top.copy(); top.putalpha(top.getchannel('A').point(lambda v: int(v * op)))
    _safe_comp(base, top, xy)


def _safe_comp(base, top, xy):
    x, y = int(round(xy[0])), int(round(xy[1]))
    x0, y0 = max(x, 0), max(y, 0); x1, y1 = min(x + top.width, base.width), min(y + top.height, base.height)
    if x1 <= x0 or y1 <= y0: return
    base.alpha_composite(top.crop((x0 - x, y0 - y, x1 - x, y1 - y)), (x0, y0))


def add_light(base, layer, k=1.0):
    """加法發光：layer 為 RGBA，以 alpha 乘色後加到 base"""
    a = np.asarray(layer).astype(np.float32); b = np.asarray(base).astype(np.float32)
    rgb = a[..., :3] * (a[..., 3:4] / 255.0) * k
    b[..., :3] = np.minimum(b[..., :3] + rgb, 255)
    base.paste(Image.fromarray(b.astype(np.uint8), 'RGBA'))


# ───────────────────────── 背景 ─────────────────────────
def bg_solid(c=NAVY):
    def f(x): x.img.paste(c + (255,), (0, 0, W, H))
    return f


def bg_grad(c1, c2, ang=90):
    g = np.linspace(0, 1, H)[:, None, None] if ang == 90 else np.linspace(0, 1, W)[None, :, None]
    arr = (np.array(c1)[None, None] * (1 - g) + np.array(c2)[None, None] * g)
    arr = np.broadcast_to(arr, (H, W, 3)).astype(np.uint8)
    im = Image.fromarray(np.ascontiguousarray(arr)).convert('RGBA')
    def f(x): x.img.paste(im)
    return f


VID = R + '/10_img/vid/'


@functools.lru_cache(8)
def _vid_frames(name):
    d = VID + 'f/' + name
    return sorted(glob.glob(d + '/*.jpg'))


def _grade(im, g):
    if not g: return im
    a = np.asarray(im.convert('RGB')).astype(np.float32) / 255
    if 'sat' in g: m = a.mean(2, keepdims=True); a = m + (a - m) * g['sat']
    if 'gain' in g: a = a * np.array(g['gain'])
    if 'gamma' in g: a = np.clip(a, 0, 1) ** g['gamma']
    if 'tint' in g:  # duotone：暗→c0 亮→c1
        l = a.mean(2, keepdims=True); c0, c1 = np.array(g['tint'][0]) / 255, np.array(g['tint'][1]) / 255
        a = lerp(a, c0 * (1 - l) + c1 * l, g.get('tintk', 1.0))
    if 'dark' in g: a = a * (1 - g['dark'])
    return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).convert('RGBA')


def _cover(im, z, cx, cy, flip=False):
    """以中心 (cx,cy)（0..1）、縮放 z（1=剛好蓋滿）裁出 W×H"""
    s = max(W / im.width, H / im.height) * z
    cw, ch = W / s, H / s
    x0 = min(max(cx * im.width - cw / 2, 0), max(im.width - cw, 0)); y0 = min(max(cy * im.height - ch / 2, 0), max(im.height - ch, 0))
    out = im.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + cw, y0 + ch))
    return ImageOps.mirror(out) if flip else out


def bg_vid(name, z=(1.0, 1.08), c=(0.5, 0.5), c1=None, speed=1.0, start=0.0, grade=None, flip=False, op=1.0):
    def f(x):
        fs = _vid_frames(name)
        if not fs: return
        i = int((start + x.t * speed) * FPS) % len(fs)
        fr = Image.open(fs[i]).convert('RGB')
        u = ease(x.u, 'lin'); cc = lerpt(c, c1 or c, u)
        im = _grade(_cover(fr, lerp(z[0], z[1], u), cc[0], cc[1], flip), grade)
        if op >= 1: x.img.paste(im)
        else: over(x.img, im, (0, 0), op)
    return f


def bg_img(p, z=(1.0, 1.1), c=(0.5, 0.5), c1=None, e='io', grade=None, flip=False, blur=0, vflip=False, rot=(0, 0)):
    def f(x):
        u = ease(x.u, e); cc = lerpt(c, c1 or c, u)
        src = img(p).convert('RGB')
        if vflip: src = ImageOps.flip(src)
        im = _cover(src, lerp(z[0], z[1], u), cc[0], cc[1], flip)
        r = lerp(rot[0], rot[1], u)
        if r: im = im.rotate(r, Image.BICUBIC).resize((W, H), box=(W * 0.04, H * 0.04, W * 0.96, H * 0.96))
        if blur: im = im.filter(ImageFilter.GaussianBlur(blur))
        x.img.paste(_grade(im.convert('RGBA'), grade))
    return f


def ovl_vid(name, mode='screen', op=1.0, z=1.0, c=(0.5, 0.5), speed=1.0, start=0.0, grade=None, t0=0, t1=99):
    """黑底素材疊加（火、煙火、光漏、煙）"""
    def f(x):
        if not (t0 <= x.t <= t1): return
        fs = _vid_frames(name)
        if not fs: return
        i = int((start + (x.t - t0) * speed) * FPS) % len(fs)
        im = _grade(_cover(Image.open(fs[i]).convert('RGB'), z, c[0], c[1]), grade)
        a = np.asarray(x.img).astype(np.float32); b = np.asarray(im).astype(np.float32)[..., :3] * op
        if mode == 'screen': a[..., :3] = 255 - (255 - a[..., :3]) * (255 - b) / 255
        else: a[..., :3] = np.minimum(a[..., :3] + b, 255)
        x.img.paste(Image.fromarray(a.astype(np.uint8), 'RGBA'))
    return f


def stripes(color=CYAN, ang=-25, w=40, gap=80, speed=200, op=0.15, area=None):
    """斜紋色卡（陣營感）：area=(x0,y0,x1,y1) 限定"""
    def f(x):
        L = Image.new('L', (W, H), 0); d = ImageDraw.Draw(L)
        off = (x.t * speed) % (w + gap); k = math.tan(math.radians(ang))
        for i in range(-40, 80):
            x0 = i * (w + gap) + off
            d.polygon([(x0, 0), (x0 + w, 0), (x0 + w + k * H, H), (x0 + k * H, H)], fill=int(255 * op))
        if area: m = Image.new('L', (W, H), 0); ImageDraw.Draw(m).rectangle(area, fill=255); L = ImageChops.multiply(L, m)
        lay = Image.new('RGBA', (W, H), color + (0,)); lay.putalpha(L); x.img.alpha_composite(lay)
    return f


def bars(spec):
    """色條：spec=[(x0,y0,x1,y1,color,alpha,(t_in,t_out),slide)]，slide='l'/'r'/'u'/'d' 從邊滑入"""
    def f(x):
        lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
        for (x0, y0, x1, y1, col, al, (ti, to), sl) in spec:
            if x.t < ti or x.t > to: continue
            u = ease((x.t - ti) / 0.25, 'out')
            if sl == 'l': x1 = x0 + (x1 - x0) * u
            elif sl == 'r': x0 = x1 - (x1 - x0) * u
            elif sl == 'u': y0 = y1 - (y1 - y0) * u
            elif sl == 'd': y1 = y0 + (y1 - y0) * u
            d.rectangle((x0, y0, x1, y1), fill=col + (int(al * 255),))
        x.img.alpha_composite(lay)
    return f


def panels(spec):
    """斜切分割：spec=[(poly[(x,y)...], [layers], border_color or None, (t_in, slide_dx, slide_dy))]"""
    def f(x):
        for poly, layers, bc, anim in spec:
            ti, dx, dy = anim if anim else (0, 0, 0)
            if x.t < ti: continue
            u = ease((x.t - ti) / 0.3, 'out'); off = ((1 - u) * dx, (1 - u) * dy)
            sub = Image.new('RGBA', (W, H), (0, 0, 0, 255)); c2 = Ctx(sub, x.t, x.dur, x.T, x.shot)
            for L in layers: L(c2)
            m = Image.new('L', (W, H), 0); pp = [(px + off[0], py + off[1]) for px, py in poly]
            ImageDraw.Draw(m).polygon(pp, fill=255)
            x.img.paste(sub, (0, 0), m)
            if bc: ImageDraw.Draw(x.img).line(pp + [pp[0]], fill=bc + (255,), width=8)
    return f


# ───────────────────────── 行情 ─────────────────────────
def series(sym, d0, d1):
    return [r for r in OHLC[sym] if d0 <= r[0] <= d1]


def _ylim(vals, pad=0.08):
    lo, hi = min(vals), max(vals); r = (hi - lo) or hi * 0.01
    return lo - r * pad, hi + r * pad


def fmt(v, dec=None):
    if dec is None: dec = 0 if v >= 1000 else 2
    return f'{v:,.{dec}f}'


def chart(sym, d0, d1, rev=(0, 1), box=(120, 160, 1800, 900), mode='full', span=40, color='sign', ref=None,
          width=7, glow=True, fill=True, grid=True, head=True, label=True, notes=(), e='io', cand=False, dec=None,
          ylim=None, alpha=1.0):
    """走勢線：rev=(u0,u1) 期間從頭畫到尾；mode='follow' 鏡頭跟著頭走（span 天）；notes=[(日期, 文字, 色)]"""
    rows = series(sym, d0, d1); n = len(rows)
    closes = [r[4] for r in rows]; ref = ref if ref is not None else closes[0]
    x0, y0, x1, y1 = box

    def f(x):
        p = ease((x.u - rev[0]) / max(rev[1] - rev[0], 1e-6), e) * (n - 1)
        k = int(p); fr = p - k
        lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
        if mode == 'follow':
            a = max(0.0, p - span * 0.85); b = a + span
            vis = closes[int(a):int(math.ceil(p)) + 1] or closes[:1]
            lo, hi = ylim or _ylim(vis, 0.25)
        else:
            a, b = 0, n - 1; lo, hi = ylim or _ylim(closes)
        X = lambda i: x0 + (i - a) / max(b - a, 1e-6) * (x1 - x0)
        Y = lambda v: y1 - (v - lo) / (hi - lo) * (y1 - y0)
        if grid:
            for g in range(5):
                gv = lo + (hi - lo) * g / 4; gy = Y(gv)
                d.line((x0, gy, x1, gy), fill=(120, 160, 220, 40), width=1)
                d.text((x0 + 6, gy - 28), fmt(gv, dec), font=font('mono', 20), fill=(150, 180, 230, 110))
        pts = [(X(i), Y(closes[i])) for i in range(int(max(a - 1, 0)), k + 1)]
        if k + 1 < n: pts.append((X(k + fr), Y(lerp(closes[k], closes[k + 1], fr))))
        pts = [(px, py) for px, py in pts if px >= x0 - 40]
        hv = lerp(closes[k], closes[min(k + 1, n - 1)], fr)
        col = (UP if hv >= ref else DN) if color == 'sign' else color
        if cand:
            cw = max(2, (x1 - x0) / max(b - a, 1) * 0.6)
            for i in range(int(max(a, 0)), k + 1):
                o, h_, l, c = rows[i][1:]; cx = X(i)
                if cx < x0 - 10: continue
                cc = UP if c >= o else DN
                d.line((cx, Y(h_), cx, Y(l)), fill=cc + (255,), width=2)
                d.rectangle((cx - cw / 2, Y(max(o, c)), cx + cw / 2, Y(min(o, c)) + 1), fill=cc + (255,))
        elif len(pts) >= 2:
            if fill:
                poly = pts + [(pts[-1][0], y1), (pts[0][0], y1)]
                m = Image.new('L', (W, H), 0); ImageDraw.Draw(m).polygon(poly, fill=255)
                gr = Image.new('L', (W, H), 0); ga = np.linspace(0, 90, H).astype(np.uint8)[::-1]
                gr = Image.fromarray(np.ascontiguousarray(np.broadcast_to(ga[:, None], (H, W))))
                fl = Image.new('RGBA', (W, H), col + (0,)); fl.putalpha(ImageChops.multiply(m, gr)); lay.alpha_composite(fl)
            if color == 'sign':  # 分段上色：高於參考紅、低於綠
                for (pa, pb), i in zip(zip(pts, pts[1:]), range(len(pts))):
                    v = (y1 - (pb[1] + pa[1]) / 2) / (y1 - y0) * (hi - lo) + lo
                    d.line((pa, pb), fill=(UP if v >= ref else DN) + (255,), width=width)
            else:
                d.line(pts, fill=col + (255,), width=width, joint='curve')
        # 註記
        for nd, txt, nc in notes:
            idx = next((i for i, r in enumerate(rows) if r[0] >= nd), None)
            if idx is None or idx > p: continue
            nx, ny = X(idx), Y(closes[idx]); age = (p - idx)
            if nx < x0 - 20: continue
            a_ = min(1.0, age / 3)
            d.line((nx, ny, nx, y0 - 10), fill=nc + (int(160 * a_),), width=2)
            d.ellipse((nx - 9, ny - 9, nx + 9, ny + 9), outline=nc + (255,), width=3)
            tw = d.textlength(txt, font=font('zh', 34))
            tx = min(max(nx - tw / 2, 20), W - tw - 20)
            d.rectangle((tx - 12, y0 - 62, tx + tw + 12, y0 - 14), fill=nc + (int(230 * a_),))
            d.text((tx, y0 - 64), txt, font=font('zh', 34), fill=(10, 10, 20, int(255 * a_)))
        if glow and len(pts) >= 2:
            g = lay.resize((W // 4, H // 4), Image.BILINEAR).filter(ImageFilter.GaussianBlur(6)).resize((W, H), Image.BILINEAR)
            add_light(x.img, g, 1.3 * alpha)
        if alpha < 1: lay.putalpha(lay.getchannel('A').point(lambda v: int(v * alpha)))
        x.img.alpha_composite(lay)
        if head and pts:
            hx, hy = pts[-1]; d2 = ImageDraw.Draw(x.img)
            pr = 14 + 6 * math.sin(x.t * 9)
            hl = Image.new('RGBA', (W, H), (0, 0, 0, 0)); ImageDraw.Draw(hl).ellipse((hx - 40, hy - 40, hx + 40, hy + 40), fill=col + (255,))
            add_light(x.img, hl.filter(ImageFilter.GaussianBlur(18)), 1.0)
            d2.ellipse((hx - pr / 2, hy - pr / 2, hx + pr / 2, hy + pr / 2), fill=WHITE + (255,))
            if label:
                s = fmt(hv, dec); f_ = font('num', 64); tw = d2.textlength(s, font=f_)
                bx = min(hx + 24, W - tw - 40); by = hy - 90 if hy > y0 + 120 else hy + 30
                d2.rectangle((bx - 10, by, bx + tw + 14, by + 66), fill=col + (235,))
                d2.text((bx, by - 2), s, font=f_, fill=(10, 10, 20, 255))
                dt = rows[min(int(round(p)), n - 1)][0][5:].replace('-', '/')
                d2.text((bx, by + 70 if by > hy else by - 40), dt, font=font('mono', 28), fill=(220, 230, 255, 220))
    return f


def race(syms, d0, d1, rev=(0, 1), box=(140, 170, 1500, 940), e='io', width=6, labels=True, hl=None):
    """多線競賽：年初=0%，各指數報酬率一起畫"""
    data = {}
    for s in syms:
        rows = series(s, d0, d1); base = rows[0][4]
        data[s] = [(r[0], 100 * (r[4] / base - 1)) for r in rows]
    allv = [v for s in data for _, v in data[s]]; lo, hi = _ylim(allv, 0.06)
    dates = sorted({dt for s in data for dt, _ in data[s]}); di = {dt: i for i, dt in enumerate(dates)}; N = len(dates)
    PAL = [UP, GOLD, CYAN, (190, 120, 255), (255, 140, 60), DN, (255, 255, 255), (255, 110, 200), (120, 200, 255), (200, 200, 120), (160, 255, 200)]
    x0, y0, x1, y1 = box

    def f(x):
        p = ease((x.u - rev[0]) / max(rev[1] - rev[0], 1e-6), e) * (N - 1)
        lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
        X = lambda i: x0 + i / (N - 1) * (x1 - x0); Y = lambda v: y1 - (v - lo) / (hi - lo) * (y1 - y0)
        d.line((x0, Y(0), x1, Y(0)), fill=(255, 255, 255, 110), width=2)
        d.text((x0 - 90, Y(0) - 18), '0%', font=font('mono', 28), fill=(255, 255, 255, 160))
        ends = []
        for j, s in enumerate(syms):
            col = PAL[j % len(PAL)]
            if hl and s not in hl: col = (90, 100, 130)
            pts = [(X(di[dt]), Y(v)) for dt, v in data[s] if di[dt] <= p]
            if len(pts) >= 2: d.line(pts, fill=col + (255,), width=width if not hl or s in hl else 3, joint='curve')
            if pts: ends.append((pts[-1][1], pts[-1][0], s, col, [v for dt, v in data[s] if di[dt] <= p][-1]))
        g = lay.resize((W // 4, H // 4)).filter(ImageFilter.GaussianBlur(5)).resize((W, H)); add_light(x.img, g, 1.0)
        x.img.alpha_composite(lay)
        if labels:
            d2 = ImageDraw.Draw(x.img); ends.sort(); last = -999
            for yy, xx, s, col, v in ends:
                yy = max(yy, last + 40); last = yy
                d2.ellipse((xx - 7, yy - 7, xx + 7, yy + 7), fill=col + (255,))
                d2.text((xx + 18, yy - 22), f'{NAME.get(s, s)} {v:+.1f}%', font=font('zhb', 32), fill=col + (255,))
    return f


# ───────────────────────── 角色 ─────────────────────────
@functools.lru_cache(48)
def _sprite(p, hpx, ol, crop, flip):
    """角色圖縮到 hpx 高，加外框（ol=((色, 寬), ...) 由內而外），回傳 (RGBA, pad)"""
    im = img(p)
    if crop: im = im.crop((int(crop[0] * im.width), int(crop[1] * im.height), int(crop[2] * im.width), int(crop[3] * im.height)))
    s = hpx / im.height; im2 = im.resize((max(1, int(im.width * s)), hpx), Image.LANCZOS if s < 1 else Image.BICUBIC)
    if flip: im2 = ImageOps.mirror(im2)
    if not ol: return im2, 0
    tot = sum(w for _, w in ol); pad = tot + 6
    out = Image.new('RGBA', (im2.width + 2 * pad, im2.height + 2 * pad), (0, 0, 0, 0))
    A = Image.new('L', out.size, 0); A.paste(im2.getchannel('A'), (pad, pad))
    k = 2; sm = A.resize((max(1, A.width // k), max(1, A.height // k)), Image.BOX).point(lambda v: 255 if v > 70 else 0)
    def dil(m, r): return m.filter(ImageFilter.GaussianBlur(max(0.6, r / k * 0.5))).point(lambda v: 255 if v > 14 else 0)
    def ero(m, r): return m.filter(ImageFilter.GaussianBlur(max(0.6, r / k * 0.5))).point(lambda v: 255 if v > 241 else 0)
    def up(m): return m.resize(A.size, Image.BILINEAR).filter(ImageFilter.GaussianBlur(1.0)).point(lambda v: min(255, max(0, (v - 128) * 4 + 128)))
    keep = dil(dil(ero(sm, 6), 6), 16)  # 主體附近；遠離主體的去背碎點不描邊也不畫
    sm = ImageChops.multiply(sm, keep)
    close = ero(dil(sm, 12), 12)
    inv = ImageOps.invert(close); ImageDraw.floodfill(inv, (0, 0), 0)
    close = ImageChops.lighter(close, inv)  # 補掉剪影內部的洞
    r = tot
    for col, w in reversed(ol):
        lay = Image.new('RGBA', out.size, col + (255,)); lay.putalpha(up(dil(close, r))); out.alpha_composite(lay); r -= w
    lay = Image.new('RGBA', out.size, ol[0][0] + (255,)); lay.putalpha(up(close)); out.alpha_composite(lay)
    im3 = im2.copy(); ka = up(keep).crop((pad, pad, pad + im2.width, pad + im2.height))
    im3.putalpha(ImageChops.multiply(im2.getchannel('A'), ka))
    out.alpha_composite(im3, (pad, pad))
    return out, pad


OL = ((255, 255, 255), 12), ((8, 22, 60), 10)


def char(p, xy=(0.5, 1.0), h=0.9, xy1=None, h1=None, e='out', anchor=(0.5, 1.0), flip=False, pop=0.0, t_in=0.0,
         breathe=0.006, sil=None, shadow=None, op=1.0, rot=0.0, rot1=None, crop=None, hop=None, ol=None, t_out=None):
    """角色貼圖：xy 為錨點在畫面上的位置（0..1），h 為高度（畫面高的倍數）；pop>0 彈入；sil=顏色 剪影；
    shadow=(dx,dy,color) 偏移色塊陰影；crop=(l,t,r,b) 0..1 只取局部；hop=[秒] 小跳；ol=外框（OL＝白＋藍）"""
    def f(x):
        if x.t < t_in or (t_out is not None and x.t >= t_out): return
        u = ease(x.u, e)
        base = int(round(max(h, h1 if h1 is not None else h) * H))
        spr, pad = _sprite(p, base, ol, crop, flip)
        hh = lerp(h, h1 if h1 is not None else h, u) * H
        if pop: hh *= ease((x.t - t_in) / pop, 'back') if x.t - t_in < pop else 1
        hh *= 1 + breathe * math.sin(x.t * 2 * math.pi / 2.6)
        if hh < 4: return
        sc = hh / base
        im2 = spr if abs(sc - 1) < 1e-3 else spr.resize((max(1, int(spr.width * sc)), max(1, int(spr.height * sc))), Image.BILINEAR)
        pd = pad * sc
        r = lerp(rot, rot1 if rot1 is not None else rot, u)
        if r: im2 = im2.rotate(r, Image.BICUBIC, expand=True)
        px, py = lerpt(xy, xy1 or xy, u)
        dy = 0
        if hop:
            for ht in hop:
                q = (x.t - ht) / 0.28
                if 0 <= q <= 1: dy = -math.sin(q * math.pi) * 0.025 * H
        iw, ih = im2.width - 2 * pd, im2.height - 2 * pd
        X0 = px * W - anchor[0] * iw - pd; Y0 = py * H - anchor[1] * ih - pd + dy
        if shadow:
            sh = Image.new('RGBA', im2.size, shadow[2] + (255,)); sh.putalpha(im2.getchannel('A'))
            _safe_comp(x.img, sh, (X0 + shadow[0], Y0 + shadow[1]))
        if sil:
            s2 = Image.new('RGBA', im2.size, sil + (255,)); s2.putalpha(im2.getchannel('A')); im2 = s2
        if op < 1: im2 = im2.copy(); im2.putalpha(im2.getchannel('A').point(lambda v: int(v * op)))
        _safe_comp(x.img, im2, (X0, Y0))
    return f


def swap(frames, **k):
    """關鍵張切換：frames=[(t, path, kwargs)]，每段時間畫對應的圖（做出動作感）"""
    fs = [(t, char(p, **{**k, **kk})) for t, p, kk in frames]
    def f(x):
        cur = None
        for t, fn in fs:
            if x.t >= t: cur = fn
        if cur: cur(x)
    return f


# ───────────────────────── 文字 ─────────────────────────
def txt(s, xy=(0.5, 0.5), size=120, fk='zh', col=WHITE, anchor='mm', t_in=0.0, t_out=None, anim='pop', box=None,
        stroke=0, sc=(0, 0, 0), op=1.0, track=0, shadow=None):
    """anim: pop（彈出）／type（打字）／slide（左滑入）／cut（直接）／rise（下往上）"""
    def f(x):
        if x.t < t_in or (t_out is not None and x.t > t_out): return
        q = x.t - t_in; ss = s
        if anim == 'type': ss = s[:max(1, int(q / 0.05))]
        fk_ = 'zhb' if fk in ('num', 'osw', 'mono') and any(ord(ch) > 0x7e for ch in s) else fk
        F = font(fk_, size); d = ImageDraw.Draw(x.img)
        bb = d.textbbox((0, 0), ss, font=F, anchor='lt'); tw, th = bb[2] - bb[0], bb[3] - bb[1]
        pad = int(size * 0.25)
        lay = Image.new('RGBA', (tw + pad * 2 + stroke * 2 + 8, th + pad * 2 + stroke * 2 + 8), (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
        if box: dl.rectangle((0, 0, lay.width, lay.height), fill=box)
        if shadow: dl.text((pad + stroke + shadow[0], pad + stroke + shadow[1]), ss, font=F, fill=shadow[2] + (255,), anchor='lt')
        dl.text((pad + stroke, pad + stroke), ss, font=F, fill=col + (255,), anchor='lt', stroke_width=stroke, stroke_fill=sc)
        sc_ = 1.0; dx = dy = 0; a = op
        if anim == 'pop': sc_ = ease(q / 0.22, 'back') if q < 0.22 else 1
        elif anim == 'slide': dx = -(1 - ease(q / 0.3, 'out')) * 300; a *= min(1, q / 0.2)
        elif anim == 'rise': dy = (1 - ease(q / 0.35, 'out')) * 80; a *= min(1, q / 0.25)
        if t_out is not None and t_out - x.t < 0.15: a *= max(0, (t_out - x.t) / 0.15)
        if sc_ <= 0.02: return
        if sc_ != 1: lay = lay.resize((max(1, int(lay.width * sc_)), max(1, int(lay.height * sc_))), Image.BILINEAR)
        if a < 1: lay.putalpha(lay.getchannel('A').point(lambda v: int(v * a)))
        ax = {'l': 0, 'm': 0.5, 'r': 1}[anchor[0]]; ay = {'t': 0, 'm': 0.5, 'b': 1}[anchor[1]]
        _safe_comp(x.img, lay, (xy[0] * W - ax * lay.width + dx, xy[1] * H - ay * lay.height + dy))
    return f


def counter(v0, v1, xy=(0.5, 0.5), size=260, col=WHITE, rev=(0, 0.8), dec=0, pre='', suf='', e='out', fk='num', stroke=0, sc=(0, 0, 0), shadow=None):
    def f(x):
        u = ease((x.u - rev[0]) / max(rev[1] - rev[0], 1e-6), e)
        v = lerp(v0, v1, u); s = f'{pre}{v:,.{dec}f}{suf}' if not isinstance(v0, str) else v0
        txt(s, xy, size, fk, col, anim='cut', stroke=stroke, sc=sc, shadow=shadow)(x)
    return f


def ticker(syms_date, y=1080 - 54, speed=260, op=0.92):
    """底部跑馬燈：顯示 syms_date 那天的真實收盤與漲跌"""
    items = []
    for s in ['TWII', 'SOX', 'IXIC', 'GSPC', 'N225', 'KS11', 'GC_F', 'BTC-USD', 'CL_F', 'NVDA', '2330.TW']:
        rows = [r for r in OHLC[s] if r[0] <= syms_date]
        if len(rows) < 2: continue
        c, pc = rows[-1][4], rows[-2][4]; ch = 100 * (c / pc - 1)
        items.append((NAME[s], fmt(c), ch))

    def f(x):
        d = ImageDraw.Draw(x.img); d.rectangle((0, y, W, y + 54), fill=(4, 8, 20, int(255 * op)))
        d.line((0, y, W, y), fill=CYAN + (180,), width=2)
        off = -(x.T * speed) % 4000; xx = -off
        while xx < W:
            for nm, v, ch in items:
                col = UP if ch >= 0 else DN
                d.text((xx, y + 8), nm, font=font('zhb', 30), fill=(230, 235, 255, 255)); xx += d.textlength(nm, font=font('zhb', 30)) + 14
                s = f'{v} {"▲" if ch >= 0 else "▼"}{abs(ch):.2f}%'
                d.text((xx, y + 10), s, font=font('mono', 28), fill=col + (255,)); xx += d.textlength(s, font=font('mono', 28)) + 60
    return f


def datestamp(s, xy=(60, 50), size=54, col=CYAN):
    def f(x):
        d = ImageDraw.Draw(x.img)
        d.rectangle((xy[0] - 14, xy[1] - 6, xy[0] + 10, xy[1] + size + 6), fill=col + (255,))
        d.text((xy[0] + 26, xy[1] - 4), s, font=font('num', size + 8), fill=WHITE + (255,))
    return f


# ───────────────────────── 粒子 ─────────────────────────
def parts(kind='bubbles', n=60, seed=1, area=(0, 0, W, H), speed=1.0, col=None, size=(6, 26), op=1.0, t0=0.0):
    """bubbles 上升泡泡／confetti 紅金彩帶／coins 金幣落下／embers 火星／rain 雨絲／dust 漂浮光點／bills 鈔票綠紙片"""
    rnd = random.Random(seed)
    P = [dict(x=rnd.random(), y=rnd.random(), s=rnd.uniform(*size), v=rnd.uniform(0.5, 1.5), ph=rnd.random() * 6.28,
              c=rnd.choice([UP, GOLD, (255, 255, 255), CYAN]) if col is None else col) for _ in range(n)]

    def f(x):
        tt = (x.t - t0) * speed
        if tt < 0: return
        lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
        ax0, ay0, ax1, ay1 = area; aw, ah = ax1 - ax0, ay1 - ay0
        for p in P:
            if kind == 'bubbles':
                yy = (p['y'] - tt * 0.12 * p['v']) % 1.0; xx = p['x'] + 0.01 * math.sin(tt * 2 + p['ph'])
                X, Y, r = ax0 + xx * aw, ay0 + yy * ah, p['s']
                d.ellipse((X - r, Y - r, X + r, Y + r), outline=(200, 235, 255, int(170 * op)), width=2)
                d.ellipse((X - r * 0.45, Y - r * 0.6, X - r * 0.1, Y - r * 0.25), fill=(255, 255, 255, int(200 * op)))
            elif kind in ('confetti', 'bills'):
                yy = (p['y'] + tt * 0.22 * p['v']) % 1.15 - 0.1; xx = p['x'] + 0.03 * math.sin(tt * 1.7 + p['ph'])
                X, Y, r = ax0 + xx * aw, ay0 + yy * ah, p['s']
                fl = abs(math.cos(tt * 5 * p['v'] + p['ph'])); a = math.radians(p['ph'] * 57 + tt * 90)
                ww, hh = r * (1.6 if kind == 'bills' else 0.6), r * fl * (0.8 if kind == 'bills' else 1)
                cs, sn = math.cos(a), math.sin(a)
                pts = [(X + cs * dx - sn * dy, Y + sn * dx + cs * dy) for dx, dy in ((-ww, -hh), (ww, -hh), (ww, hh), (-ww, hh))]
                cc = (90, 170, 110) if kind == 'bills' else p['c']
                d.polygon(pts, fill=cc + (int(255 * op),))
            elif kind == 'coins':
                yy = (p['y'] + tt * 0.35 * p['v']) % 1.2 - 0.1; X, Y, r = ax0 + p['x'] * aw, ay0 + yy * ah, p['s']
                fl = abs(math.cos(tt * 6 + p['ph']))
                d.ellipse((X - r * fl, Y - r, X + r * fl, Y + r), fill=GOLD + (int(255 * op),), outline=(180, 120, 20, 255), width=2)
            elif kind == 'embers':
                yy = (p['y'] - tt * 0.18 * p['v']) % 1.0; xx = p['x'] + 0.02 * math.sin(tt * 3 + p['ph'])
                X, Y, r = ax0 + xx * aw, ay0 + yy * ah, p['s'] * 0.25
                d.ellipse((X - r, Y - r, X + r, Y + r), fill=(255, 150 + int(80 * math.sin(p['ph'])), 60, int(230 * op)))
            elif kind == 'rain':
                yy = (p['y'] + tt * 1.6 * p['v']) % 1.0; X, Y = ax0 + p['x'] * aw, ay0 + yy * ah
                d.line((X, Y, X - 8, Y + 40 * p['v']), fill=(190, 210, 240, int(120 * op)), width=2)
            elif kind == 'dust':
                xx = (p['x'] + tt * 0.01 * p['v']) % 1; yy = (p['y'] + 0.02 * math.sin(tt + p['ph'])) % 1
                X, Y, r = ax0 + xx * aw, ay0 + yy * ah, p['s'] * 0.18
                a = 0.5 + 0.5 * math.sin(tt * 2 + p['ph'])
                d.ellipse((X - r, Y - r, X + r, Y + r), fill=(p['c'] if col else CYAN) + (int(200 * a * op),))
        if kind in ('embers', 'dust', 'coins'):
            add_light(x.img, lay.filter(ImageFilter.GaussianBlur(4)), 0.8)
        x.img.alpha_composite(lay)
    return f


def ring(t_at, xy=(0.5, 0.5), col=WHITE, dur=0.45, r1=1100, w=26):
    """衝擊波圓環"""
    def f(x):
        q = (x.t - t_at) / dur
        if not 0 <= q <= 1: return
        r = r1 * ease(q, 'out'); a = int(255 * (1 - q))
        lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); cx, cy = xy[0] * W, xy[1] * H
        ImageDraw.Draw(lay).ellipse((cx - r, cy - r, cx + r, cy + r), outline=col + (a,), width=max(2, int(w * (1 - q))))
        add_light(x.img, lay, 1.0)
    return f


def speedlines(t0=0, t1=99, col=WHITE, n=70, seed=3, center=(0.5, 0.5), op=0.5):
    """集中線"""
    rnd = random.Random(seed); L = [(rnd.random() * 6.283, rnd.uniform(0.3, 0.7), rnd.uniform(4, 14)) for _ in range(n)]
    def f(x):
        if not t0 <= x.t <= t1: return
        lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(lay); cx, cy = center[0] * W, center[1] * H
        k = int(x.t * 24) % 3
        for i, (a, r0, w) in enumerate(L):
            if (i + k) % 3 == 0: continue
            a2 = a + 0.012
            R0 = r0 * 1100; R1 = 1600
            d.polygon([(cx + math.cos(a) * R0, cy + math.sin(a) * R0), (cx + math.cos(a) * R1, cy + math.sin(a) * R1),
                       (cx + math.cos(a2) * R1, cy + math.sin(a2) * R1)], fill=col + (int(255 * op),))
        x.img.alpha_composite(lay)
    return f


def vignette(k=0.55):
    yy, xx = np.mgrid[0:H, 0:W]; r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    m = Image.fromarray((np.clip(r - 0.55, 0, 1) / 0.9 * 255 * k).clip(0, 255).astype(np.uint8))
    lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); lay.putalpha(m)
    def f(x): x.img.alpha_composite(lay)
    return f


# ───────────────────────── 全片後製 ─────────────────────────
def post(im, T, EV, rnd):
    """EV=[(t, kind, k)]：flash 閃白、black 黑、glitch 故障、shake 震、punch 推近、red/green 色閃"""
    a = None; sx = sy = 0; zoom = 1.0
    for t, kind, k in EV:
        q = T - t
        if q < 0 or q > 0.6: continue
        if kind == 'shake' and q < 0.35:
            amp = 28 * k * (1 - q / 0.35) ** 2; sx += amp * math.sin(q * 90); sy += amp * math.cos(q * 70)
        if kind == 'vshake' and q < 0.45:
            sy += 46 * k * (1 - q / 0.45) ** 2 * math.cos(q * 75)
        if kind == 'punch' and q < 0.3: zoom *= 1 + 0.06 * k * (1 - q / 0.3) ** 2
    if zoom != 1 or sx or sy:
        zoom = max(zoom, 1 / (1 - 2 * abs(sx) / W) + 0.004, 1 / (1 - 2 * abs(sy) / H) + 0.004)
        cw, ch = W / zoom, H / zoom
        sx = max(-(W - cw) / 2, min((W - cw) / 2, sx)); sy = max(-(H - ch) / 2, min((H - ch) / 2, sy))
        im = im.resize((W, H), Image.BILINEAR, box=((W - cw) / 2 - sx, (H - ch) / 2 - sy, (W + cw) / 2 - sx, (H + ch) / 2 - sy))
    for t, kind, k in EV:
        q = T - t
        if q < 0 or q > 0.6: continue
        if kind == 'rgb' and q < 0.35:
            arr = np.asarray(im).copy(); s_ = int(16 * k * (1 - q / 0.35) + 1)
            arr[..., 0] = np.roll(arr[..., 0], s_, 1); arr[..., 2] = np.roll(arr[..., 2], -s_, 0); im = Image.fromarray(arr)
        if kind == 'glitch' and q < 0.2:
            arr = np.asarray(im).copy(); s = int(18 * k)
            arr[..., 0] = np.roll(arr[..., 0], s, 1); arr[..., 2] = np.roll(arr[..., 2], -s, 1)
            for _ in range(int(6 * k)):
                y0 = rnd.randint(0, H - 60); h_ = rnd.randint(10, 80); arr[y0:y0 + h_] = np.roll(arr[y0:y0 + h_], rnd.randint(-120, 120), 1)
            im = Image.fromarray(arr)
        if kind in ('flash', 'red', 'green', 'gold', 'black') and q < 0.18:
            col = {'flash': WHITE, 'red': UP, 'green': DN, 'gold': GOLD, 'black': (0, 0, 0)}[kind]
            a = (1 - q / 0.18) * k
            im = Image.blend(im, Image.new(im.mode, im.size, col + ((255,) if im.mode == 'RGBA' else ())), min(1, a))
    return im


def grain(im, rnd, k=6):
    n = np.random.default_rng(rnd.randint(0, 1 << 30)).normal(0, k, (H // 2, W // 2)).astype(np.int16)
    n = np.repeat(np.repeat(n, 2, 0), 2, 1)
    a = np.asarray(im).astype(np.int16); a[..., :3] += n[..., None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


class Shot:
    def __init__(s, dur, layers, name=''):
        s.dur, s.layers, s.name = dur, layers, name


def headline(date, s, xy=(70, 110), t_in=0.0, col=CYAN, size=54, sub=None):
    """新聞標籤：日期色塊＋標題，從左滑入"""
    def f(x):
        q = x.t - t_in
        if q < 0: return
        u = ease(q / 0.3, 'out'); d = ImageDraw.Draw(x.img)
        Fd, Fs = font('num' if date.isascii() else 'zh', size + 6 if date.isascii() else size - 4), font('zh', size)
        dw = d.textlength(date, font=Fd) + 30; sw = d.textlength(s, font=Fs) + 40
        X = xy[0] - (1 - u) * (dw + sw + 100); Y = xy[1]
        lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
        dl.rectangle((X, Y, X + dw, Y + size + 26), fill=col + (255,))
        dl.text((X + 15, Y + 4), date, font=Fd, fill=(5, 10, 26, 255))
        dl.rectangle((X + dw, Y, X + dw + sw * min(1, q / 0.35), Y + size + 26), fill=(5, 10, 26, 225))
        if q > 0.15: dl.text((X + dw + 20, Y + 4), s, font=Fs, fill=WHITE + (255,))
        if sub and q > 0.3:
            nb = sub.replace(' ', '').replace('%', '').replace('+', '').replace('-', '').replace('.', '').replace(',', '').isdigit()
            Fb = font('num', int(size * 1.1)) if nb else font('zhb', int(size * 0.62)); hb = int(size * 1.1) if nb else int(size * 0.62)
            sw2 = d.textlength(sub, font=Fb) + 30
            dl.rectangle((X, Y + size + 26, X + sw2, Y + size + 26 + hb + 20), fill=(255, 255, 255, 235))
            dl.text((X + 15, Y + size + 30 - (4 if nb else 0)), sub, font=Fb, fill=(UP if sub.startswith('+') else DN if sub.startswith('-') else (5, 10, 26)) + (255,))
        x.img.alpha_composite(lay)
    return f


def rankbars(items, rev=(0.05, 0.6), box=(120, 150, 1800, 1000), t_in=0.0, hl=None):
    """年度漲跌排行：items=[(名稱, %)]；中軸在 box 中央偏左，正值紅向右、負值綠向左"""
    items = sorted(items, key=lambda r: -r[1]); n = len(items)
    vmax = max(abs(v) for _, v in items)
    x0, y0, x1, y1 = box; ax = x0 + (x1 - x0) * 0.42; sc = (x1 - ax - 220) / vmax
    rh = (y1 - y0) / n

    def f(x):
        d = ImageDraw.Draw(x.img)
        d.line((ax, y0 - 10, ax, y1), fill=(255, 255, 255, 160), width=3)
        for i, (nm, v) in enumerate(items):
            ui = ease((x.u - rev[0] - i * 0.025) / max(rev[1] - rev[0], 1e-6), 'out')
            if ui <= 0: continue
            yy = y0 + i * rh; vv = v * ui; col = UP if v >= 0 else DN
            if hl and nm not in hl: col = tuple(int(c * 0.45) for c in col)
            bx0, bx1 = (ax, ax + vv * sc) if v >= 0 else (ax + vv * sc, ax)
            d.rectangle((bx0, yy + rh * 0.14, bx1, yy + rh * 0.86), fill=col + (255,))
            F = font('zhb', int(rh * 0.5)); Fn = font('num', int(rh * 0.72))
            s = f'{vv:+.1f}%'
            if v >= 0:
                d.text((ax - 20, yy + rh / 2), nm, font=F, fill=WHITE + (255,), anchor='rm')
                d.text((bx1 + 16, yy + rh / 2), s, font=Fn, fill=col + (255,), anchor='lm')
            else:
                d.text((ax + 20, yy + rh / 2), nm, font=F, fill=WHITE + (255,), anchor='lm')
                d.text((bx0 - 16, yy + rh / 2), s, font=Fn, fill=col + (255,), anchor='rm')
    return f


def flatline(t_flat=1.0, col=DN, y=0.5):
    """心電圖：跳動後拉平"""
    def f(x):
        lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
        head = min(W, x.t / 2.4 * W); pts = []
        for px in range(0, int(head), 6):
            tt = px / W * 2.4; v = 0
            if tt < t_flat:
                ph = (tt * 1.6) % 1
                v = (-1.0 if 0.40 < ph < 0.45 else 0.7 if 0.45 < ph < 0.5 else -0.15 if 0.5 < ph < 0.56 else 0) * (1 - tt / t_flat * 0.5)
            pts.append((px, y * H + v * 260))
        if len(pts) > 1: d.line(pts, fill=col + (255,), width=6)
        if pts: d.ellipse((pts[-1][0] - 10, pts[-1][1] - 10, pts[-1][0] + 10, pts[-1][1] + 10), fill=WHITE + (255,))
        add_light(x.img, lay.filter(ImageFilter.GaussianBlur(10)), 1.2); x.img.alpha_composite(lay)
    return f


def intraday(path, rev=(0, 1), box=(140, 220, 1780, 900), col=UP, notes=()):
    """ANT 首日 5 分線"""
    rows = [r for r in json.load(open(R + '/' + path)) if r[0] >= '11-19 09:40']
    vals = [r[1] for r in rows]; lo, hi = _ylim(vals, 0.1); n = len(vals); x0, y0, x1, y1 = box

    def f(x):
        p = ease((x.u - rev[0]) / (rev[1] - rev[0]), 'io') * (n - 1); k = int(p)
        X = lambda i: x0 + i / (n - 1) * (x1 - x0); Y = lambda v: y1 - (v - lo) / (hi - lo) * (y1 - y0)
        pts = [(X(i), Y(vals[i])) for i in range(k + 1)]
        lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
        if len(pts) > 1: d.line(pts, fill=col + (255,), width=6, joint='curve')
        add_light(x.img, lay.resize((W // 4, H // 4)).filter(ImageFilter.GaussianBlur(5)).resize((W, H)), 1.2)
        x.img.alpha_composite(lay)
        if pts:
            d2 = ImageDraw.Draw(x.img); hx, hy = pts[-1]
            d2.ellipse((hx - 9, hy - 9, hx + 9, hy + 9), fill=WHITE + (255,))
            s = f'{vals[k]:.2f}'; d2.text((hx + 20, hy - 70), s, font=font('num', 72), fill=WHITE + (255,))
            d2.text((hx + 20, hy + 10), rows[k][0][6:], font=font('mono', 28), fill=(200, 220, 255, 220))
    return f


GLOB = []  # 全片疊層（字幕、年度進度條），在後製前畫；ctx.t = 全片時間


def frame(shots, EV, T):
    t0 = 0.0
    for sh in shots:
        if T < t0 + sh.dur or sh is shots[-1]:
            im = Image.new('RGBA', (W, H), (0, 0, 0, 255)); x = Ctx(im, T - t0, sh.dur, T, sh)
            for L in sh.layers: L(x)
            rnd = random.Random(int(T * 1000))
            im = post(im.convert('RGB'), T, EV, rnd).convert('RGBA')
            g = Ctx(im, T, 1e9, T, sh)
            for L in GLOB: L(g)
            return grain(im.convert('RGB'), rnd, 5)
        t0 += sh.dur


def lyrics(lines, y=0.885, size=50):
    """lines=[(t0, t1, 文字)] 或 [(t0, t1, 唱完秒, 文字)]：卡拉 OK 式由左到右點亮，唱完那一刻亮滿"""
    def f(x):
        for L in lines:
            t0, t1, s = L[0], L[1], L[-1]; te = L[2] if len(L) == 4 else t0 + (t1 - t0) * 0.8
            if not t0 <= x.t < t1: continue
            F = font('zh', size); d = ImageDraw.Draw(x.img)
            tw = d.textlength(s, font=F); X = W / 2 - tw / 2; Y = y * H - size / 2
            a = min(1, (x.t - t0) / 0.12, (t1 - x.t) / 0.12)
            lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
            dl.text((X, Y), s, font=F, fill=(255, 255, 255, int(235 * a)), stroke_width=5, stroke_fill=(0, 10, 30, int(200 * a)))
            # 點亮進度（青色覆蓋）
            p = min(1, (x.t - t0 - 0.25) / max(0.1, te - t0 - 0.25))
            if p <= 0: p = 0
            hl = Image.new('RGBA', (W, H), (0, 0, 0, 0)); dh = ImageDraw.Draw(hl)
            dh.text((X, Y), s, font=F, fill=CYAN + (int(255 * a),))
            m = Image.new('L', (W, H), 0); ImageDraw.Draw(m).rectangle((X, 0, X + tw * p, H), fill=255)
            lay.paste(hl, (0, 0), ImageChops.multiply(m, hl.getchannel('A')))
            x.img.alpha_composite(lay)
    return f


def yearbar(keys, spans, y=34):
    """年度進度條：keys=[(T, 'YYYY-MM-DD')] 分段線性；spans=[(T0,T1)] 只在這些時間顯示"""
    import datetime as dt
    D = lambda s: dt.date.fromisoformat(s).toordinal()
    d0, d1 = D('2026-01-01'), D('2026-12-31')
    x0, x1 = 300, W - 300

    def f(x):
        if not any(a <= x.t < b for a, b in spans): return
        k = [(t, D(s)) for t, s in keys]
        if x.t <= k[0][0]: cur = k[0][1]
        elif x.t >= k[-1][0]: cur = k[-1][1]
        else:
            for (ta, da), (tb, db) in zip(k, k[1:]):
                if ta <= x.t < tb: cur = da + (db - da) * (x.t - ta) / (tb - ta); break
        a = min(1, min(x.t - a_ for a_, b_ in spans if a_ <= x.t < b_) / 0.3)
        lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
        d.line((x0, y, x1, y), fill=(255, 255, 255, int(70 * a)), width=2)
        px = x0 + (cur - d0) / (d1 - d0) * (x1 - x0)
        d.line((x0, y, px, y), fill=CYAN + (int(230 * a),), width=4)
        for m in range(1, 13):
            mx = x0 + (D(f'2026-{m:02d}-01') - d0) / (d1 - d0) * (x1 - x0)
            d.line((mx, y - 6, mx, y + 6), fill=(255, 255, 255, int(110 * a)), width=2)
            d.text((mx + 4, y + 8), f'{m}', font=font('mono', 16), fill=(255, 255, 255, int(110 * a)))
        d.ellipse((px - 7, y - 7, px + 7, y + 7), fill=WHITE + (int(255 * a),))
        ds = dt.date.fromordinal(int(cur)).strftime('%Y.%m.%d')
        d.text((x0 - 250, y - 22), ds, font=font('num', 46), fill=WHITE + (int(240 * a),))
        x.img.alpha_composite(lay)
    return f


def render(shots, EV, out, a, b, fast=False):
    """渲染 [a,b) 秒到 out（無聲 mp4）"""
    import subprocess
    n0, n1 = int(round(a * FPS)), int(round(b * FPS))
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                          '-c:v', 'libx264', '-preset', 'fast' if fast else 'medium', '-crf', '16', '-pix_fmt', 'yuv420p', out], stdin=subprocess.PIPE)
    import time; t_ = time.time()
    for i in range(n0, n1):
        p.stdin.write(frame(shots, EV, i / FPS).tobytes())
        if (i - n0) % 48 == 0: print(f'{out} {i - n0}/{n1 - n0} {(time.time() - t_) / max(i - n0, 1):.2f}s/f', flush=True)
    p.stdin.close(); p.wait()


# ═════════════════════════ v2：K 棒、局部切鏡、錢幣特效、報價牆 ═════════════════════════
def _seg(g, pts):
    """g∈[0,1] 沿 pts 折線等分走"""
    n = len(pts) - 1; q = min(max(g, 0), 1) * n; i = min(int(q), n - 1); return lerp(pts[i], pts[i + 1], q - i)


def kbar(sym=None, d0=None, d1=None, rows=None, t0=0.0, step=None, pre=0, rev=(0, 1), e='lin', box=(110, 150, 1700, 930),
         span=None, ma=5, vol=True, grid=True, tag=True, dec=None, cw=0.64, glow=1.0, thr=4.0, title=None, title_col=CYAN,
         ref=None, hdr=True, bgpanel=0.0, lab_dates=True, grow=0.7, ylim=None, lab=True):
    """K 棒一根根長出：step＝每根秒數（卡拍）從 t0 起；不給 step 就用 rev 在鏡內攤開。
    pre＝開場已畫好的根數；span＝視窗根數（相機跟著最新一根）；thr＝單根漲跌超過 thr% 就打大字標籤。"""
    R_ = rows if rows is not None else series(sym, d0, d1); n = len(R_)
    cl = [r[4] for r in R_]
    mav = [sum(cl[max(0, i - ma + 1):i + 1]) / len(cl[max(0, i - ma + 1):i + 1]) for i in range(n)] if ma else None
    chg = [0.0] + [100 * (cl[i] / cl[i - 1] - 1) for i in range(1, n)]
    x0, y0, x1, y1 = box
    vb = y1 - (y1 - y0) * 0.14 if vol else y1  # 量能區上緣
    spanN = span or n

    def prog(x):
        if step: return pre + max(0.0, (x.t - t0) / step)
        return pre + ease((x.u - rev[0]) / max(rev[1] - rev[0], 1e-6), e) * (n - pre)

    def lim(k):
        a = max(0, k - spanN + 1); sub = R_[a:k + 1] or R_[:1]
        lo = min(r[3] for r in sub); hi = max(r[2] for r in sub); r_ = (hi - lo) or hi * 0.01
        return lo - r_ * 0.10, hi + r_ * 0.22

    def price(k, fr, p):
        _, o, h, l, c = R_[k]
        if p >= n: return c, h, l
        g = ease(min(1.0, fr / grow), 'out'); path = [o, l, h, c] if c >= o else [o, h, l, c]
        seen = [_seg(g * j / 12, path) for j in range(13)]
        return _seg(g, path), max(seen + [o]), min(seen + [o])

    def f(x):
        p = min(prog(x), float(n)); k = min(int(p), n - 1); fr = p - int(p) if p < n else 1.0
        if ylim: lo, hi = ylim
        else:
            la, lb = lim(max(k - 1, 0)), lim(k); g_ = ease(min(1, fr / grow), 'io') if p < n else 1
            lo, hi = lerp(la[0], lb[0], g_), lerp(la[1], lb[1], g_)
            cur_, hh_, ll_ = price(k, fr, p); lo = min(lo, ll_); hi = max(hi, hh_)
        a = max(0.0, p - spanN * 0.86) if span else 0.0
        slot = (x1 - x0) / spanN
        X = lambda i: x0 + (i - a + 0.5) * slot
        Y = lambda v: vb - (v - lo) / (hi - lo) * (vb - y0)
        lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
        if bgpanel: x.img.alpha_composite(Image.new('RGBA', (W, H), (3, 6, 16, int(255 * bgpanel))))
        if grid:
            for gi in range(6):
                gv = lo + (hi - lo) * gi / 5; gy = Y(gv)
                d.line((x0, gy, x1, gy), fill=(110, 140, 200, 40), width=1)
                d.text((x1 + 14, gy - 14), fmt(gv, dec), font=font('mono', 22), fill=(150, 175, 220, 130))
        bw = max(2.0, slot * cw)
        for i in range(int(max(0, a - 1)), k + 1):
            xc = X(i)
            if xc < x0 - slot or xc > x1 + slot: continue
            o = R_[i][1]
            if i == k: cc, hh, ll = price(k, fr, p)
            else: _, o, hh, ll, cc = R_[i]
            col = UP if cc >= o else DN
            d.line((xc, Y(hh), xc, Y(ll)), fill=col + (255,), width=max(2, int(bw * 0.14)))
            ya, yb = sorted((Y(o), Y(cc)))
            d.rectangle((xc - bw / 2, ya, xc + bw / 2, max(yb, ya + 3)), fill=col + (255,))
            if vol:
                vh = min(1.0, abs(chg[i]) / 6 + 0.12) * (y1 - vb - 8)
                if i == k and p < n: vh *= ease(min(1, fr / grow), 'out')
                d.rectangle((xc - bw / 2, y1 - vh, xc + bw / 2, y1), fill=col + (110,))
        if ma and k >= 1:
            pts = [(X(i), Y(mav[i])) for i in range(int(max(0, a - 1)), k + 1) if X(i) >= x0 - slot]
            if p < n and pts: pts[-1] = (pts[-1][0], Y(lerp(mav[max(k - 1, 0)], mav[k], ease(min(1, fr / grow)))))
            if len(pts) > 1: d.line(pts, fill=GOLD + (200,), width=3, joint='curve')
        if glow:
            gl = lay.resize((W // 4, H // 4), Image.BILINEAR).filter(ImageFilter.GaussianBlur(5)).resize((W, H), Image.BILINEAR)
            add_light(x.img, gl, glow)
        x.img.alpha_composite(lay)
        d2 = ImageDraw.Draw(x.img)
        cur, _, _ = price(k, fr, p)
        pc = R_[k - 1][4] if k else R_[0][1]
        col = UP if cur >= pc else DN
        if tag:
            yy = Y(cur)
            for xx in range(int(x0), int(x1), 26): d2.line((xx, yy, xx + 13, yy), fill=col + (170,), width=2)
            s = fmt(cur, dec); F = font('num', 46); tw = d2.textlength(s, font=F)
            d2.rectangle((x1 + 4, yy - 26, x1 + tw + 26, yy + 26), fill=col + (255,))
            d2.text((x1 + 14, yy - 25), s, font=F, fill=(8, 10, 20, 255))
        if hdr:
            nm = title or NAME.get(sym, sym or '')
            d2.text((x0, y0 - 100), nm, font=font('zh', 52), fill=title_col + (255,))
            tw = d2.textlength(nm, font=font('zh', 52))
            if lab_dates: d2.text((x0 + tw + 26, y0 - 88), R_[k][0][5:].replace('-', '.'), font=font('num', 52), fill=(200, 215, 240, 230))
            base = ref if ref is not None else pc
            q = 100 * (cur / base - 1); s = f'{q:+.2f}%'
            F = font('num', 62); tw2 = d2.textlength(s, font=F)
            d2.rectangle((x1 - tw2 - 30, y0 - 100, x1 + 6, y0 - 26), fill=(UP if q >= 0 else DN) + (235,))
            d2.text((x1 - tw2 - 12, y0 - 102), s, font=F, fill=(8, 10, 20, 255))
        if lab:  # 大漲大跌標籤：長完那一刻打上
            for i in range(k, max(0, k - 5), -1):
                if abs(chg[i]) < thr: continue
                age = p - i - grow
                if age < 0: continue
                if age > 3.0: break
                up = chg[i] > 0; colb = UP if up else DN
                sc_ = ease(min(1, age / 0.3), 'back') if age < 0.3 else 1.0
                sz = int(110 * max(sc_, 0.05)); s = f'{chg[i]:+.2f}%'; F = font('num', sz)
                xc = X(i); tw = d2.textlength(s, font=F); bx = min(max(xc - tw / 2, x0), x1 - tw)
                by = Y(R_[i][2]) - sz - 30 if up else Y(R_[i][3]) + 30
                by = min(max(by, y0 - 6), vb - sz - 10)
                d2.rectangle((bx - 14, by + 6, bx + tw + 14, by + sz + 2), fill=colb + (240,))
                d2.text((bx, by), s, font=F, fill=WHITE + (255,))
                break
    f.n = n; f.rows = R_; f.chg = chg
    return f


def k_done(t0, step, i, pre=0, grow=0.7):
    """第 i 根（0 起）長完的時刻（鏡內秒）"""
    return t0 + (i - pre + grow) * step


@functools.lru_cache(4)
def _coin(sz=128):
    S_ = sz * 2; im = Image.new('RGBA', (S_, S_), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    for r in range(S_ // 2, 0, -1):
        q = r / (S_ / 2); col = (int(255 - 40 * q), int(214 - 70 * q), int(90 - 60 * q), 255)
        d.ellipse((S_ / 2 - r, S_ / 2 - r, S_ / 2 + r, S_ / 2 + r), fill=col)
    d.ellipse((10, 10, S_ - 10, S_ - 10), outline=(150, 95, 10, 255), width=10)
    d.ellipse((30, 30, S_ - 30, S_ - 30), outline=(255, 236, 160, 255), width=5)
    F = ImageFont.truetype(FONTS['osw'], int(S_ * 0.62))
    d.text((S_ / 2 + 4, S_ / 2 + 6), '$', font=F, fill=(140, 85, 5, 255), anchor='mm')
    d.text((S_ / 2, S_ / 2), '$', font=F, fill=(255, 240, 180, 255), anchor='mm')
    d.ellipse((S_ * 0.22, S_ * 0.16, S_ * 0.48, S_ * 0.32), fill=(255, 255, 240, 120))
    return im.resize((sz, sz), Image.LANCZOS)


def money(kind='bill', n=40, seed=1, mode='fall', origin=(0.5, 0.6), t0=0.0, speed=1.0, size=(70, 150), op=1.0, area=(0, 0, W, H), spin=1.0, t1=99):
    """真鈔票（Mixkit 實拍去背）／金幣 sprite：mode='fall' 由上灑落、'burst' 從 origin 噴出後落下、'rise' 由下往上"""
    rnd = random.Random(seed)
    P = [dict(x=rnd.random(), y=rnd.random(), s=rnd.uniform(*size), v=rnd.uniform(0.6, 1.4), ph=rnd.random() * 6.28,
              rot=rnd.uniform(0, 360), vr=rnd.uniform(-160, 160), ang=rnd.uniform(-2.7, -0.45), sp=rnd.uniform(900, 2000), dl=rnd.uniform(0, 0.12)) for _ in range(n)]
    src = img('10_img/fx/bill.png') if kind == 'bill' else _coin(128)
    srcm = ImageOps.mirror(src)

    def f(x):
        tt = (x.t - t0) * speed
        if tt < 0 or x.t > t1: return
        lay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        ax0, ay0, ax1, ay1 = area; aw, ah = ax1 - ax0, ay1 - ay0
        for p in P:
            if mode == 'burst':
                q = tt - p['dl']
                if q < 0: continue
                X = origin[0] * W + math.cos(p['ang']) * p['sp'] * q * 0.75
                Y = origin[1] * H + math.sin(p['ang']) * p['sp'] * q * 0.75 + 1300 * q * q
                if Y > H + 200: continue
            elif mode == 'rise':
                X = ax0 + (p['x'] + 0.02 * math.sin(tt * 1.5 + p['ph'])) * aw; Y = ay0 + ((p['y'] - tt * 0.22 * p['v']) % 1.25 - 0.1) * ah
            else:
                X = ax0 + (p['x'] + 0.03 * math.sin(tt * 1.3 + p['ph'])) * aw; Y = ay0 + ((p['y'] + tt * 0.26 * p['v']) % 1.3 - 0.15) * ah
            s = p['s']; fl = math.cos(tt * 4.5 * p['v'] * spin + p['ph'])
            w_ = max(2, int(s * (abs(fl) * 0.85 + 0.15)))
            h_ = int(s) if kind == 'coin' else max(2, int(s * src.height / src.width))
            im = (srcm if (fl < 0 and kind == 'bill') else src).resize((w_, h_), Image.BILINEAR)
            im = im.rotate(p['rot'] + p['vr'] * tt, Image.BILINEAR, expand=True)
            if op < 1: im.putalpha(im.getchannel('A').point(lambda v: int(v * op)))
            _safe_comp(lay, im, (X - im.width / 2, Y - im.height / 2))
        if kind == 'coin': add_light(x.img, lay.resize((W // 4, H // 4)).filter(ImageFilter.GaussianBlur(4)).resize((W, H)), 0.6)
        x.img.alpha_composite(lay)
    return f


@functools.lru_cache(16)
def _graded(p, gk):
    g = dict(gk)
    if 'tint' in g: g['tint'] = tuple(tuple(c) for c in g['tint'])
    if 'gain' in g: g['gain'] = tuple(g['gain'])
    im = img(p); a = im.getchannel('A'); out = _grade(im, g); out.putalpha(a); return out


def _gkey(g):
    return tuple(sorted((k, tuple(tuple(c) if isinstance(c, (list, tuple)) else c for c in v) if isinstance(v, (list, tuple)) else v) for k, v in g.items()))


def cuts(p, seq, flip=False, grade=None, e='lin'):
    """同一張圖的局部切鏡：seq=[(t, (cx,cy), z, (dx,dy), dz)]，每段硬切到另一局部並慢漂。
    z＝相對「剛好蓋滿畫面」的放大倍數（4＝只看 1/4 寬）。RGBA 去背圖直接疊在現有底上。"""
    def f(x):
        cur = None
        for i, s in enumerate(seq):
            if x.t >= s[0]: cur = (i, s)
        if cur is None: return
        i, (ts, c, z, dxy, dz) = cur
        te = seq[i + 1][0] if i + 1 < len(seq) else x.dur
        u = ease((x.t - ts) / max(te - ts, 1e-3), e)
        src = _graded(p, _gkey(grade)) if grade else img(p)
        cx, cy = c[0] + dxy[0] * u, c[1] + dxy[1] * u; zz = z + dz * u
        s_ = max(W / src.width, H / src.height) * zz; cw, ch = W / s_, H / s_
        x0 = min(max(cx * src.width - cw / 2, 0), max(src.width - cw, 0)); y0 = min(max(cy * src.height - ch / 2, 0), max(src.height - ch, 0))
        out = src.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + cw, y0 + ch))
        if flip: out = ImageOps.mirror(out)
        x.img.alpha_composite(out)
    return f


@functools.lru_cache(8)
def _wall(seed, cols, rows):
    rnd = random.Random(seed)
    syms = ['TSMC', 'NVDA', 'SOX', 'NDX', 'SPX', 'N225', 'KOSPI', 'TWSE', 'GOLD', 'BTC', 'WTI', 'HYNIX', 'SMSN', 'AVGO', 'AMD', 'ASML', 'MU', 'ARM', 'ANT', 'TSLA', 'META', 'MSFT', 'AAPL', 'GOOG']
    return [(rnd.choice(syms), rnd.uniform(20, 3000), rnd.uniform(-9, 9), rnd.random()) for _ in range(cols * rows)]


def wall(bias=0.0, seed=4, cols=6, rows=11, op=0.55, flick=6.0, speed=40):
    """報價牆：滿版代號、價格、漲跌，數字隨時間閃動；bias>0 偏紅（漲），<0 偏綠（跌）"""
    cells = _wall(seed, cols, rows); cwid, chh = W / cols, H / rows

    def f(x):
        lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
        off = (x.T * speed) % chh
        for j in range(rows + 1):
            for i in range(cols):
                sy, pv, ch_, ph = cells[(j % rows) * cols + i]
                tick = int(x.T * flick + ph * 10)
                r_ = random.Random(tick * 131 + j * 17 + i)
                c2 = ch_ * 0.5 + bias * 6 + r_.uniform(-1.5, 1.5)
                col = UP if c2 >= 0 else DN
                X, Y = i * cwid + 18, j * chh - off
                if r_.random() < 0.08: d.rectangle((X - 8, Y + 4, X + cwid - 22, Y + chh - 6), fill=col + (int(80 * op),))
                d.text((X, Y + 10), sy, font=font('mono', 30), fill=(200, 210, 235, int(200 * op)))
                d.text((X + cwid * 0.40, Y + 8), f'{pv * (1 + c2 / 100):,.2f}', font=font('mono', 30), fill=(235, 240, 255, int(170 * op)))
                d.text((X + cwid * 0.40, Y + 44), f'{"▲" if c2 >= 0 else "▼"}{abs(c2):.2f}%', font=font('zhb', 26), fill=col + (int(255 * op),))
        x.img.alpha_composite(lay)
    return f


def slam(s, xy=(0.5, 0.5), size=300, col=WHITE, t_in=0.0, t_out=None, fk='num', box=None, sk=1.8, shadow=(14, 14, (0, 0, 0)), stroke=0, sc=(0, 0, 0)):
    """大字砸進來：從 sk 倍縮到 1，3 格內完成"""
    base = txt(s, xy, size, fk, col, t_in=t_in, t_out=t_out, anim='cut', box=box, shadow=shadow, stroke=stroke, sc=sc)

    def f(x):
        q = x.t - t_in
        if q < 0 or (t_out is not None and x.t > t_out): return
        if q >= 0.125: return base(x)
        z = lerp(sk, 1.0, ease(q / 0.125, 'out'))
        sub = Image.new('RGBA', (W, H), (0, 0, 0, 0)); base(Ctx(sub, x.t, x.dur, x.T, x.shot))
        cx, cy = xy[0] * W, xy[1] * H; cw, ch = W / z, H / z
        sub = sub.resize((W, H), Image.BILINEAR, box=(cx - cx / z, cy - cy / z, cx - cx / z + cw, cy - cy / z + ch))
        x.img.alpha_composite(sub)
    return f


def cardbg(c1, c2, stripe=None, ang=-25, op=0.10, speed=120):
    """色卡底：漸層＋斜紋"""
    L = [bg_grad(c1, c2)]
    if stripe: L.append(stripes(stripe, ang=ang, op=op, speed=speed))
    def f(x):
        for l in L: l(x)
    return f


def diag(col=WHITE, x_top=0.62, x_bot=0.48, w=18, t_in=0.0, op=1.0):
    """斜切白條（畫面分割線）"""
    def f(x):
        if x.t < t_in: return
        u = ease((x.t - t_in) / 0.18, 'out')
        d = ImageDraw.Draw(x.img); a, b = x_top * W, x_bot * W
        d.polygon([(a - w, 0), (a + w, 0), (b + w, H * u), (b - w, H * u)], fill=col + (int(255 * op),))
    return f
