"""render2：讀 60_cut/edl2.py（SHOTS、AMB），逐格合成交給 ffmpeg。
畫面語言：陣營色卡、人物雙層外框、特寫聚焦、節拍跳切、斜線分割、關節擺動、領土地圖、CC0 粒子（Kenney Particle Pack / Smoke Particles）。
用法: python render2.py [t0 t1] [--out f.mp4] [--frames t,t,...]"""
import sys, os, math, json, subprocess, importlib.util, glob
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops, ImageOps

ROOT = "C:/Users/user/hermes-files/ai-war-mmv"
FPS = 24; W, H = 1920, 1080
RNG = np.random.default_rng

# 陣營色：亮、主、暗
FAC = {
    "gpt": ((248, 244, 234), (200, 166, 86), (26, 24, 34)),
    "claude": ((252, 238, 214), (226, 112, 38), (36, 18, 10)),
    "ds": ((236, 244, 255), (22, 58, 140), (5, 10, 26)),
    "gemini": ((236, 230, 255), (124, 92, 206), (14, 10, 30)),
    "grok": ((255, 168, 64), (52, 36, 26), (0, 0, 0)),
    "qwen": ((214, 216, 255), (78, 66, 180), (10, 10, 32)),
    "glm": ((242, 242, 242), (176, 26, 36), (10, 10, 10)),
    "kimi": ((222, 232, 248), (64, 92, 156), (8, 10, 24)),
    "empire": ((250, 246, 236), (206, 170, 90), (22, 20, 28)),
    "alliance": ((236, 244, 255), (30, 74, 160), (6, 10, 24)),
    "fire": ((255, 226, 170), (230, 90, 20), (24, 4, 0)),
    "blood": ((255, 226, 214), (196, 20, 26), (8, 0, 0)),
    "ash": ((228, 224, 216), (112, 108, 102), (14, 14, 14)),
    "night": ((200, 220, 255), (40, 60, 120), (2, 4, 12)),
    "rain": ((214, 220, 228), (90, 100, 116), (14, 16, 20)),
    "dawn": ((255, 236, 200), (220, 160, 90), (20, 24, 44)),
    "mono": ((240, 240, 240), (120, 120, 120), (8, 8, 8)),
    "sea": ((200, 222, 246), (40, 74, 128), (4, 8, 20)),
    "lamp": ((255, 214, 150), (150, 90, 40), (10, 8, 14)),
    "gold": ((255, 236, 180), (190, 140, 60), (20, 16, 12)),
    "snow": ((238, 240, 246), (120, 126, 140), (12, 14, 20)),
}

def ease(u, k="out"):
    u = min(1.0, max(0.0, u))
    if k == "lin": return u
    if k == "snap": return 1 - (1 - u) ** 4
    if k == "in": return u * u
    if k == "io": return u * u * (3 - 2 * u)
    return 1 - (1 - u) ** 2

def lerp(a, b, u):
    return tuple(x + (y - x) * u for x, y in zip(a, b))

# ---------------- 快取 ----------------
class LRU(dict):
    def __init__(self, n): super().__init__(); self.n = n; self.order = []
    def get2(self, k, make):
        if k in self:
            self.order.remove(k); self.order.append(k); return self[k]
        v = make(); self[k] = v; self.order.append(k)
        while len(self.order) > self.n: del self[self.order.pop(0)]
        return v
_IMG = LRU(24); _CUT = LRU(16)

def img(path):
    def mk():
        p = path if os.path.isabs(path) else f"{ROOT}/{path}"
        im = Image.open(p).convert("RGB")
        if im.width > 3000: im = im.resize((3000, int(im.height * 3000 / im.width)), Image.LANCZOS)
        # 對比拉開：發灰、發白的圖把亮度 1%～99% 拉到全幅
        a = np.asarray(im).astype(np.float32); l = a.mean(-1)
        lo, hi = np.percentile(l, 1), np.percentile(l, 99.5)
        if hi - lo < 235 and hi - lo > 20:
            a = (a - lo) * (250.0 / (hi - lo))
            im = Image.fromarray(a.clip(0, 255).astype(np.uint8))
        return im
    return _IMG.get2(path, mk)

def native_size(name):
    return _IMG.get2(("ns", name), lambda: Image.open(f"{ROOT}/60_cut/cut/{name}.png").size)

def cut(name, flip=False, up=False):
    def mk():
        c = Image.open(f"{ROOT}/60_cut/cut/{name}.png").convert("RGBA")
        a = c.split()[3].point(lambda v: 0 if v < 40 else v)
        if up:
            rgb = Image.open(f"{ROOT}/60_cut/up/{name}.png").convert("RGB")
            a = a.resize(rgb.size, Image.LANCZOS)
            im = rgb.convert("RGBA"); im.putalpha(a)
        else:
            im = c; im.putalpha(a)
        return ImageOps.mirror(im) if flip else im
    return _CUT.get2((name, flip, up), mk)

def has_up(name): return os.path.exists(f"{ROOT}/60_cut/up/{name}.png")

def rig(name, ang, flip=False):
    def base():
        d = f"{ROOT}/10_assets/chars/layers/rig_{name}"
        j = json.load(open(d + "/rig.json"))
        return Image.open(d + "/body.png").convert("RGBA"), Image.open(d + "/weapon.png").convert("RGBA"), tuple(j["grip"])
    b, w, g = _CUT.get2(("rigbase", name), base)
    a = int(round(ang))
    def mk():
        out = Image.alpha_composite(b, w.rotate(a, resample=Image.BICUBIC, center=g))
        return ImageOps.mirror(out) if flip else out
    return _CUT.get2(("rig", name, a, flip), mk)

# ---------------- 精靈圖（CC0） ----------------
PDIR = f"{ROOT}/10_assets/vfx_src/particle/PNG/"
SDIR = f"{ROOT}/10_assets/vfx_src/smoke/PNG/"
_SPR = LRU(400)
def spr_mask(n):
    def mk():
        im = Image.open(PDIR + n + ".png").convert("RGBA")
        a = np.asarray(im).astype(np.float32)
        lum = a[..., :3].mean(-1) * a[..., 3] / 255
        return Image.fromarray(lum.clip(0, 255).astype(np.uint8))
    return _SPR.get2(n, mk)
def spr_rgba(path):
    return _SPR.get2(path, lambda: Image.open(SDIR + path + ".png").convert("RGBA"))
def spr_scaled(key, src, size, rot=0):
    def mk():
        m = src.resize(size, Image.BILINEAR)
        return m.rotate(rot, resample=Image.BILINEAR, expand=True) if rot else m
    return _SPR.get2((key, size, rot), mk)

def add_glow(layer, mask, col, cx, cy, amt=1.0):
    """把亮度遮罩以 col 色加到 layer（加色合成）。"""
    w, h = mask.size; x0, y0 = int(cx - w / 2), int(cy - h / 2)
    box = (max(0, x0), max(0, y0), min(W, x0 + w), min(H, y0 + h))
    if box[2] <= box[0] or box[3] <= box[1]: return
    m = mask.crop((box[0] - x0, box[1] - y0, box[2] - x0, box[3] - y0))
    if amt < 0.999: m = m.point(lambda v, a=amt: int(v * a))
    tile = Image.new("RGB", m.size, col)
    blk = Image.new("RGB", m.size, (0, 0, 0))
    reg = layer.crop(box)
    layer.paste(ImageChops.add(reg, Image.composite(tile, blk, m)), box)

def put_rgba(fr, im, cx, cy, amt=1.0):
    w, h = im.size; x0, y0 = int(cx - w / 2), int(cy - h / 2)
    if amt < 0.999:
        im = im.copy(); im.putalpha(im.split()[3].point(lambda v, a=amt: int(v * a)))
    fr.paste(im, (x0, y0), im)

# ---------------- 背景：色卡 ----------------
_YX = np.mgrid[0:H, 0:W].astype(np.float32)
def card(fac, pat, t, seed=0):
    lt, mn, dk = [np.array(c, np.float32) for c in FAC[fac]]
    y, x = _YX
    if pat == "solid":
        return Image.new("RGB", (W, H), FAC[fac][2])
    if pat == "light":
        return Image.new("RGB", (W, H), FAC[fac][0])
    if pat in ("stripes", "stripes_r"):
        ang = math.radians(62 if pat == "stripes" else 118)
        u = x * math.cos(ang) + y * math.sin(ang) + t * 60 + seed * 37
        bw = 150.0
        k = np.floor(u / bw) % 3
        out = np.where((k == 0)[..., None], mn, dk)
        e = (u % bw) < 7
        out = np.where(e[..., None], lt, out)
        return Image.fromarray(out.astype(np.uint8))
    if pat == "split":
        u = (x - W * 0.5) * 0.9 - (y - H * 0.5) * 0.45
        out = np.where((u > 0)[..., None], mn, dk)
        out = np.where((np.abs(u) < 6)[..., None], lt, out)
        return Image.fromarray(out.astype(np.uint8))
    if pat == "rays":
        a = np.arctan2(y - H * 0.5, x - W * 0.5) + t * 0.15 + seed
        k = (np.floor(a / (math.pi / 18)) % 2) == 0
        out = np.where(k[..., None], mn, dk)
        return Image.fromarray(out.astype(np.uint8))
    if pat == "bars":
        r = RNG(seed + int(t * 2))
        im = Image.new("RGB", (W, H), FAC[fac][2]); d = ImageDraw.Draw(im)
        for i in range(7):
            yy = r.uniform(0, H); hh = r.uniform(8, 90)
            d.rectangle([0, yy, W, yy + hh], fill=FAC[fac][1] if i % 3 else FAC[fac][0])
        return im
    raise ValueError(pat)

def duotone(im, fac, amt=1.0):
    lt, mn, dk = [np.array(c, np.float32) for c in FAC[fac]]
    a = np.asarray(im).astype(np.float32)
    l = (a[..., 0] * 0.3 + a[..., 1] * 0.59 + a[..., 2] * 0.11) / 255
    l = np.clip((l - 0.06) / 0.88, 0, 1)[..., None]
    lo = dk + (mn - dk) * np.clip(l * 2, 0, 1)
    out = np.where(l < 0.5, lo, mn + (lt - mn) * np.clip(l * 2 - 1, 0, 1))
    if amt < 1: out = a * (1 - amt) + out * amt
    return Image.fromarray(out.clip(0, 255).astype(np.uint8))

def img_bg(path, f, flip=False):
    im = img(path)
    if flip: im = _IMG.get2((path, "flip"), lambda: ImageOps.mirror(img(path)))
    cx, cy, z = f[:3]
    s = max(W / im.width, H / im.height) * z
    w, h = W / s, H / s
    l = min(max(0, cx * im.width - w / 2), im.width - w); t = min(max(0, cy * im.height - h / 2), im.height - h)
    return im.resize((W, H), Image.BICUBIC, box=(l, t, l + w, t + h))

# ---------------- 地圖 ----------------
REG = {  # 名稱: (x, y)
    "帝都": (0.27, 0.40), "長牆": (0.43, 0.42), "星塔": (0.36, 0.13), "無旗營": (0.58, 0.20), "北原": (0.76, 0.24),
    "鯨骨港": (0.86, 0.62), "千問港": (0.70, 0.84), "月夜林": (0.62, 0.62), "赤原": (0.53, 0.46), "帝國軍港": (0.30, 0.80),
    "西境": (0.10, 0.30), "南嶺": (0.16, 0.66),
}
RKEYS = list(REG)
_MAP = {}
def map_base():
    if _MAP: return _MAP
    r = RNG(5)
    def fbm():
        acc = np.zeros((H, W), np.float32)
        for o, a in ((6, 1.0), (12, 0.5), (24, 0.25), (48, 0.12)):
            n = r.standard_normal((o * 9 // 16 + 2, o + 2)).astype(np.float32)
            acc += a * np.asarray(Image.fromarray(n).resize((W, H), Image.BICUBIC))
        return acc
    y, x = _YX / np.array([H, W], np.float32)[:, None, None]
    land = 0.85 - 1.25 * np.clip(x - 0.80, 0, 1) - 1.6 * np.clip(y - 0.86, 0, 1) - 0.9 * np.clip(0.05 - x, 0, 1) + 0.16 * fbm()
    land = land > 0.6
    pts = np.array([REG[k] for k in RKEYS], np.float32)
    d = (x[None] - pts[:, 0, None, None]) ** 2 + ((y[None] - pts[:, 1, None, None]) * 0.56) ** 2
    d += 0.0006 * fbm()[None]
    lab = np.argmin(d, 0).astype(np.int16)
    lab[~land] = -1
    edge = np.zeros((H, W), bool)
    edge[:, 1:] |= lab[:, 1:] != lab[:, :-1]; edge[1:, :] |= lab[1:, :] != lab[:-1, :]
    coast = Image.fromarray((land * 255).astype(np.uint8)).filter(ImageFilter.FIND_EDGES).filter(ImageFilter.MaxFilter(3))
    hatch = ((x * W + y * H) % 22 < 1.5) & ~land
    _MAP.update(lab=lab, edge=edge & land, coast=np.asarray(coast) > 0, hatch=hatch, land=land)
    return _MAP

def map_frame(m, lt):
    b = map_base()
    own = m.get("own", {})
    cols = np.zeros((len(RKEYS) + 1, 3), np.float32)
    cols[-1] = (8, 14, 30)
    for i, k in enumerate(RKEYS):
        f = own.get(k)
        cols[i] = (np.array(FAC[f][1]) * 0.55 + np.array(FAC[f][2]) * 0.45) if f else (52, 50, 46)
    burn = m.get("burn", [])
    for k in burn:
        u = ease(lt / 0.8)
        cols[RKEYS.index(k)] = np.array(cols[RKEYS.index(k)]) * (1 - u) + np.array((150, 20, 10)) * u
    out = cols[b["lab"]]
    out[b["hatch"]] = (24, 34, 60)
    out[b["edge"]] = (230, 226, 214)
    out[b["coast"]] = (240, 236, 224)
    fr = Image.fromarray(out.astype(np.uint8))
    d = ImageDraw.Draw(fr, "RGBA")
    for rt in m.get("routes", []):
        pts, col, wd, t0, dur = rt
        u = ease((lt - t0) / dur, "io")
        if u <= 0: continue
        P = [(REG[p][0] * W, REG[p][1] * H) if isinstance(p, str) else (p[0] * W, p[1] * H) for p in pts]
        L = [math.dist(P[i], P[i + 1]) for i in range(len(P) - 1)]; tot = sum(L) * u; q = [P[0]]
        for i, l in enumerate(L):
            if tot <= 0: break
            v = min(1, tot / l); q.append(lerp(P[i], P[i + 1], v)); tot -= l
        d.line(q, fill=col + (255,), width=wd, joint="curve")
        if u < 1 or True:
            hx, hy = q[-1]; d.ellipse([hx - wd * 1.4, hy - wd * 1.4, hx + wd * 1.4, hy + wd * 1.4], fill=col + (255,))
    fz = font("zhb", 30)
    for k in m.get("pins", RKEYS):
        x, y = REG[k][0] * W, REG[k][1] * H
        f = own.get(k); c = FAC[f][0] if f else (230, 230, 230)
        hl = k in m.get("hl", [])
        r = 16 if hl else 9
        if hl:
            pr = 16 + 40 * ((lt * 1.2) % 1); d.ellipse([x - pr, y - pr, x + pr, y + pr], outline=c + (int(220 * (1 - (lt * 1.2) % 1)),), width=4)
        d.ellipse([x - r, y - r, x + r, y + r], fill=c + (255,), outline=(0, 0, 0, 255), width=3)
        if m.get("labels", True):
            d.text((x + 22, y - 18), k, font=fz, fill=(250, 248, 240, 255), stroke_width=4, stroke_fill=(0, 0, 0, 255))
    cx, cy, z = m.get("f", (0.5, 0.5, 1.0))
    if z != 1.0:
        w, h = W / z, H / z
        l = min(max(0, cx * W - w / 2), W - w); t = min(max(0, cy * H - h / 2), H - h)
        fr = fr.resize((W, H), Image.BICUBIC, box=(l, t, l + w, t + h))
    return fr

# ---------------- 人物 ----------------
def char_rgba(c, lt):
    """回傳 (RGBA 來源圖, 原生寬高, 來源相對原生的倍率)。"""
    if "rig" in c:
        a0, a1, dur = c.get("swing", (0, 0, 0.2))
        ang = a0 + (a1 - a0) * ease(lt / max(dur, 1e-3), "snap")
        im = rig(c["rig"], ang, c.get("flip", False)); return im, im.size, 1.0
    name = c["p"]
    if "seq" in c:
        for dt, nm in c["seq"]:
            if lt >= dt: name = nm
    nw, nh = native_size(name)
    up = c.get("up", "auto")
    return name, (nw, nh), up

def place(src, k, cx, cy, s, sx, sy):
    """src 以原生座標 (cx,cy) 對到螢幕 (sx,sy)，原生縮放 s；src 是原生的 k 倍大。"""
    iw, ih = src.size
    sk = s / k
    l = cx * iw - sx * W / sk; t = cy * ih - sy * H / sk; r = l + W / sk; b = t + H / sk
    L, T, R, B = max(0, l), max(0, t), min(iw, r), min(ih, b)
    if R <= L or B <= T: return None
    dx, dy = int(round((L - l) * sk)), int(round((T - t) * sk))
    dw, dh = max(1, int(round((R - L) * sk))), max(1, int(round((B - T) * sk)))
    return src.resize((dw, dh), Image.BICUBIC, box=(L, T, R, B)), (dx, dy)

def draw_char(fr, c, lt, dur, shot_fac):
    u = ease(lt / max(dur, 1e-3), c.get("ease", "lin"))
    f0 = c["f0"]; f1 = c.get("f1", f0)
    cx, cy, z, sx, sy = lerp(f0, f1, u)
    res = char_rgba(c, lt)
    if isinstance(res[0], str):
        name, (nw, nh), up = res
        s = (-z) * H / nh if z < 0 else z * W / nw
        use_up = (up is True) or (up == "auto" and s > 1.25 and has_up(name))
        src = cut(name, c.get("flip", False), use_up)
        k = src.size[0] / nw
    else:
        src, (nw, nh), k = res
        s = (-z) * H / nh if z < 0 else z * W / nw
    p = place(src, k, cx, cy, s, sx, sy)
    if not p: return fr
    im, (dx, dy) = p
    if c.get("spin"):  # 打飛時旋轉（繞自身中心）
        a0, a1 = c["spin"]; ang = a0 + (a1 - a0) * u
        w0, h0 = im.size; im = im.rotate(ang, resample=Image.BICUBIC, expand=True)
        dx -= (im.width - w0) // 2; dy -= (im.height - h0) // 2
    a = Image.new("L", (W, H), 0); a.paste(im.split()[3], (dx, dy))
    if c.get("sil"):
        im = Image.new("RGBA", im.size, tuple(c["sil"]) + (255,)); im.putalpha(a.crop((dx, dy, dx + im.width, dy + im.height)))
    elif c.get("dim"):
        r, g, b, al = im.split(); dm = c["dim"]
        im = Image.merge("RGBA", (*[ch.point(lambda v: int(v * dm)) for ch in (r, g, b)], al))
    ol = c.get("ol", (5, 4))
    fac = c.get("fac", shot_fac)
    if ol and ol[0]:
        m = a.point(lambda v: 255 if v > 90 else 0)
        sm = m.resize((W // 2, H // 2), Image.BILINEAR)
        if ol[1]:
            oc = sm.filter(ImageFilter.GaussianBlur(ol[0] + ol[1])).point(lambda v: 255 if v > 8 else 0).resize((W, H), Image.BILINEAR)
            fr.paste(FAC[fac][1] if c.get("olc") is None else c["olc"], (0, 0), oc)
        ow = sm.filter(ImageFilter.GaussianBlur(ol[0])).point(lambda v: 255 if v > 8 else 0).resize((W, H), Image.BILINEAR)
        fr.paste(FAC[fac][0], (0, 0), ow)
    fr.paste(im, (dx, dy), im)
    return fr

# ---------------- 粒子（全域時間，跨鏡連續） ----------------
def vfx(fr, kind, t, amt=1.0, seed=0, col=None):
    r = RNG(seed + 1000)
    if kind == "embers":
        n = int(70 * amt); add = Image.new("RGB", (W, H)); d = ImageDraw.Draw(add)
        X = r.uniform(0, W, n); V = r.uniform(70, 220, n); P = r.uniform(0, 100, n); S = r.uniform(2, 6, n); F = r.uniform(0.5, 2, n)
        for i in range(n):
            y = H + 30 - ((t * V[i] + P[i] * 13) % (H + 60)); x = X[i] + 40 * math.sin(t * F[i] + P[i])
            fl = 0.6 + 0.4 * math.sin(t * 9 * F[i] + P[i])
            c = col or (255, int(150 + 60 * fl), 60)
            d.ellipse([x - S[i], y - S[i], x + S[i], y + S[i]], fill=tuple(int(v * fl) for v in c))
        add = ImageChops.add(add.filter(ImageFilter.GaussianBlur(3)), add)
        return ImageChops.screen(fr, add)
    if kind == "sparks":
        add = Image.new("RGB", (W, H))
        names = ["spark_01", "spark_02", "spark_03", "spark_04", "star_04", "star_06"]
        for i in range(int(14 * amt)):
            ph = (t * r.uniform(0.6, 1.4) + r.uniform(0, 1)) % 1
            x = r.uniform(0, W) + (ph - 0.5) * r.uniform(-400, 400); y = r.uniform(0.2, 1) * H - ph * r.uniform(100, 500)
            sz = int(r.uniform(60, 180) * (1 - ph * 0.6))
            add_glow(add, spr_scaled(names[i % 6], spr_mask(names[i % 6]), (sz, sz)), (255, 200, 120), x, y, 1 - ph)
        return ImageChops.screen(fr, add)
    if kind == "smoke":
        fr = fr.convert("RGBA")
        for i in range(int(6 * amt)):
            nm = "Black smoke/blackSmoke%02d" % (i * 4 % 25)
            sz = int(r.uniform(900, 1500)); vx = r.uniform(-40, 40)
            x = (r.uniform(0, W) + t * vx) % (W + sz) - sz / 2; y = r.uniform(0.15, 0.95) * H - t * 8 % 200
            put_rgba(fr, spr_scaled(nm, spr_rgba(nm), (sz, sz)), x, y, 0.32 * (col[0] / 255 if col else 1))
        return fr.convert("RGB")
    if kind == "flames":
        add = Image.new("RGB", (W, H))
        names = ["fire_01", "fire_02", "flame_01", "flame_03", "flame_04", "flame_05"]
        k = int(t * 12)
        for i in range(int(9 * amt)):
            nm = names[(i + k) % 6]; hh = int(r.uniform(380, 620) * (0.85 + 0.15 * math.sin(t * 7 + i)))
            add_glow(add, spr_scaled(nm, spr_mask(nm), (int(hh * 0.8), hh)), col or (255, 120, 30), r.uniform(0, W), H - hh * 0.32, 0.85)
        return ImageChops.screen(fr, add)
    if kind == "rain":
        ov = Image.new("RGBA", (W, H)); d = ImageDraw.Draw(ov)
        n = int(420 * amt)
        X = r.uniform(-200, W + 200, n); P = r.uniform(0, 1, n); L = r.uniform(30, 80, n)
        for i in range(n):
            y = ((t * 2200 + P[i] * (H + 200)) % (H + 200)) - 100; x = X[i] - (y * 0.12)
            d.line([(x, y), (x - L[i] * 0.12, y + L[i])], fill=(220, 228, 240, 90), width=2)
        fr = fr.convert("RGBA"); fr.alpha_composite(ov); return fr.convert("RGB")
    if kind in ("ash", "snow"):
        ov = Image.new("RGBA", (W, H)); d = ImageDraw.Draw(ov)
        n = int(160 * amt)
        X = r.uniform(0, W, n); P = r.uniform(0, 1, n); S = r.uniform(1.5, 4.5, n); V = r.uniform(30, 90, n)
        c = (235, 235, 235) if kind == "snow" else (200, 196, 190)
        for i in range(n):
            y = ((t * V[i] + P[i] * H) % (H + 40)) - 20; x = X[i] + 30 * math.sin(t * 0.7 + P[i] * 9)
            d.ellipse([x - S[i], y - S[i], x + S[i], y + S[i]], fill=c + (170,))
        fr = fr.convert("RGBA"); fr.alpha_composite(ov); return fr.convert("RGB")
    if kind == "pages":
        ov = Image.new("RGBA", (W, H)); d = ImageDraw.Draw(ov)
        for i in range(int(22 * amt)):
            dep = r.uniform(0.35, 1.0)
            ph = (t * r.uniform(0.07, 0.13) * (0.6 + dep) + r.uniform(0, 1)) % 1
            x = r.uniform(0, W) + 90 * math.sin(t * 0.8 + i * 1.7); y = -60 + ph * (H + 120)
            a = t * r.uniform(0.8, 2.2) + i; flipv = math.cos(t * r.uniform(1.5, 3.5) + i)
            w, h = 11 * dep * 2.6, 15 * dep * 2.6 * (0.25 + 0.75 * abs(flipv))
            ca, sa = math.cos(a), math.sin(a)
            pts = [(x + ca * dx - sa * dy, y + sa * dx + ca * dy) for dx, dy in ((-w, -h), (w, -h), (w, h), (-w, h))]
            sh = int(170 + 75 * abs(flipv) * dep)
            d.polygon(pts, fill=(sh, int(sh * 0.93), int(sh * 0.8), int(140 + 90 * dep)))
            if dep > 0.7:  # 字行
                for k in range(3):
                    o = -h * 0.5 + k * h * 0.4
                    d.line([(x + ca * -w * 0.6 - sa * o, y + sa * -w * 0.6 + ca * o), (x + ca * w * 0.6 - sa * o, y + sa * w * 0.6 + ca * o)], fill=(60, 40, 30, 120), width=1)
        ov = ov.filter(ImageFilter.GaussianBlur(0.8))
        fr = fr.convert("RGBA"); fr.alpha_composite(ov); return fr.convert("RGB")
    if kind == "speed":
        ov = Image.new("RGBA", (W, H)); d = ImageDraw.Draw(ov)
        r2 = RNG(seed + int(t * 24))
        for i in range(int(46 * amt)):
            y = r2.uniform(0, H); x = r2.uniform(-300, W); L = r2.uniform(200, 900)
            d.line([(x, y), (x + L, y)], fill=(col or (255, 255, 255)) + (int(r2.uniform(60, 200)),), width=int(r2.uniform(2, 7)))
        fr = fr.convert("RGBA"); fr.alpha_composite(ov); return fr.convert("RGB")
    if kind == "focus":
        ov = Image.new("RGBA", (W, H)); d = ImageDraw.Draw(ov)
        r2 = RNG(seed + int(t * 12)); c = col or (255, 255, 255)
        for i in range(int(90 * amt)):
            a = r2.uniform(0, 2 * math.pi); r0 = r2.uniform(0.42, 0.6) * W; da = r2.uniform(0.004, 0.014)
            pts = [(W / 2 + math.cos(a) * 1400, H / 2 + math.sin(a) * 1400), (W / 2 + math.cos(a - da) * r0, H / 2 + math.sin(a - da) * r0 * 0.6),
                   (W / 2 + math.cos(a + da) * 1400, H / 2 + math.sin(a + da) * 1400)]
            d.polygon(pts, fill=c + (int(r2.uniform(120, 230)),))
        fr = fr.convert("RGBA"); fr.alpha_composite(ov); return fr.convert("RGB")
    return fr

# ---------------- 打擊事件（鏡內時間） ----------------
def events(fr, s, lt):
    shake = (0.0, 0.0); zoom = 1.0
    for ev in s.get("ev", []):
        t0, kind = ev[0], ev[1]; dt = lt - t0
        if dt < 0: continue
        nf = dt * FPS
        if kind == "tap":
            x, y = ev[2] if len(ev) > 2 else (0.5, 0.5)
            if nf < 4:
                nm = "slash_0%d" % (1 + int(t0 * 7) % 4); sz = int(W * 0.7 * (1 + nf * 0.06))
                add = Image.new("RGB", (W, H))
                add_glow(add, spr_scaled(nm, spr_mask(nm), (sz, sz), int(t0 * 97) % 360), (255, 245, 230), x * W, y * H, 0.7 * (1 - nf / 4))
                fr = ImageChops.screen(fr, add)
            if nf < 4: zoom = max(zoom, 1 + 0.02 * (1 - nf / 4) ** 2)
        if kind in ("hit", "heavy"):
            x, y = ev[2] if len(ev) > 2 else (0.5, 0.5)
            if nf < 5:
                nm = "slash_0%d" % (1 + int(t0 * 7) % 4)
                sz = int(W * 0.9 * (1 + nf * 0.06))
                add = Image.new("RGB", (W, H))
                add_glow(add, spr_scaled(nm, spr_mask(nm), (sz, sz), int(t0 * 97) % 360), (255, 250, 240), x * W, y * H, 1 - nf / 5)
                ring = int(200 + nf * 260)
                add_glow(add, spr_scaled("circle_05", spr_mask("circle_05"), (ring, ring)), (255, 230, 200), x * W, y * H, max(0, 0.8 - nf / 6))
                fr = ImageChops.screen(fr, add)
            if nf < 1: fr = Image.blend(fr, Image.new("RGB", (W, H), (255, 255, 255)), 0.75 if kind == "heavy" else 0.45)
            if kind == "heavy" and 1 <= nf < 2: fr = ImageOps.invert(fr)
            if nf < 7:
                a = (24 if kind == "heavy" else 10) * (1 - nf / 7) ** 1.5
                shake = (shake[0] + math.sin(nf * 2.7) * a, shake[1] + math.cos(nf * 3.3) * a * 0.7)
                zoom = max(zoom, 1 + (0.07 if kind == "heavy" else 0.045) * (1 - nf / 7) ** 2)
        elif kind == "flash":
            if nf < 4: fr = Image.blend(fr, Image.new("RGB", (W, H), (255, 255, 255)), 0.9 * (1 - nf / 4))
        elif kind == "black":
            if nf < ev[2]: fr = Image.new("RGB", (W, H))
        elif kind == "boom":
            x, y = ev[2]
            if nf < 9:
                im = spr_rgba("Explosion/explosion%02d" % int(nf))
                sz = int((W * ev[3] if len(ev) > 3 else W * 0.7) * (0.7 + 0.05 * nf))
                ex = spr_scaled("Explosion/explosion%02d" % int(nf), im, (sz, sz))
                rgb = Image.new("RGB", ex.size); rgb.paste(ex.convert("RGB"), (0, 0), ex.split()[3])
                lay = Image.new("RGB", (W, H)); lay.paste(rgb, (int(x * W - sz / 2), int(y * H - sz / 2)))
                fr = ImageChops.screen(fr, lay)
                if nf < 3: fr = ImageChops.screen(fr, Image.new("RGB", (W, H), tuple(int(v * (1 - nf / 3) * 0.6) for v in (255, 200, 140))))
            if nf < 6:
                a = 20 * (1 - nf / 6); shake = (shake[0] + math.sin(nf * 2.9) * a, shake[1] + math.cos(nf * 3.1) * a)
        elif kind == "white_out":
            u = ease((lt - t0) / ev[2], "in")
            fr = Image.blend(fr, Image.new("RGB", (W, H), (255, 255, 255)), min(1, u))
        elif kind == "white_in":
            u = 1 - ease((lt - t0) / ev[2], "out")
            if u > 0: fr = Image.blend(fr, Image.new("RGB", (W, H), (255, 255, 255)), u)
        elif kind == "fade_in":
            u = 1 - ease((lt - t0) / ev[2], "lin")
            if u > 0: fr = Image.blend(fr, Image.new("RGB", (W, H)), u)
        elif kind == "fade_out":
            u = ease((lt - t0) / ev[2], "lin")
            fr = Image.blend(fr, Image.new("RGB", (W, H)), min(1, u))
        elif kind == "redsil":
            if nf < 2:
                l = fr.convert("L").point(lambda v: 255 if v > 110 else 0)
                fr = Image.composite(Image.new("RGB", (W, H), (255, 255, 255)), Image.new("RGB", (W, H), (200, 10, 10)), l)
    if zoom != 1.0 or shake != (0.0, 0.0):
        # 留邊隨震幅一起衰減，結束時回到 1.0，不會在最後一格跳一下
        mag = max(abs(shake[0]) / (W * 0.5), abs(shake[1]) / (H * 0.5))
        z = zoom * (1 + mag * 1.15); w, h = W / z, H / z
        l = (W - w) / 2 - shake[0] / z; t = (H - h) / 2 - shake[1] / z
        fr = fr.resize((W, H), Image.BILINEAR, box=(l, t, l + w, t + h))
    return fr

# ---------------- 字卡 ----------------
_F = {}
def font(kind, size):
    k = (kind, size)
    if k not in _F:
        if kind in ("zh", "zhb", "zhl"):
            f = ImageFont.truetype("C:/Windows/Fonts/NotoSerifTC-VF.ttf", size)
            f.set_variation_by_name({"zh": "Bold", "zhb": "Black", "zhl": "Medium"}[kind])
        else:
            f = ImageFont.truetype("C:/Windows/Fonts/constan.ttf", size)
        _F[k] = f
    return _F[k]

def text(fr, tx, lt, fac):
    st = tx["k"]; a0 = tx.get("at", 0.0)
    if lt < a0: return fr
    u = lt - a0
    if "out" in tx and lt > tx["out"]: return fr
    lc, mc, dc = FAC[tx.get("fac", fac)]
    d = ImageDraw.Draw(fr, "RGBA")
    if st == "name":
        sl = ease(u / 0.22, "snap"); off = (1 - sl) * -700
        y0 = H * 0.70
        d.polygon([(off, y0 - 10), (off + W * 0.56, y0 - 10), (off + W * 0.50, y0 + 170), (off, y0 + 170)], fill=mc + (235,))
        d.line([(off, y0 - 22), (off + W * 0.60, y0 - 22)], fill=lc + (255,), width=5)
        d.text((off + 90, y0 - 4), tx["big"], font=font("zhb", 104), fill=lc + (255,), stroke_width=3, stroke_fill=dc + (255,))
        d.text((off + 96, y0 + 122), tx["sub"], font=font("zh", 34), fill=lc + (255,))
    elif st == "place":
        a = int(255 * min(1, u / 0.3))
        d.line([(80, 86), (80, 166)], fill=mc + (a,), width=8)
        d.text((104, 80), tx["big"], font=font("zhb", 44), fill=(250, 248, 240, a), stroke_width=3, stroke_fill=(0, 0, 0, a))
        d.text((106, 134), tx["sub"], font=font("zh", 28), fill=(225, 222, 214, a), stroke_width=2, stroke_fill=(0, 0, 0, a))
    elif st in ("inner", "line"):
        s = tx["big"]; n = len(s) if st == "line" else int(min(len(s), u / max(0.03, min(0.06, 0.9 / len(s)))) + 1)
        f = font("zhl" if st == "inner" else "zh", tx.get("size", 54))
        full = d.textbbox((0, 0), s, font=f); x = W / 2 - (full[2] - full[0]) / 2; y = H * tx.get("y", 0.80)
        a = int(255 * min(1, u / 0.15))
        d.text((x, y), s[:n], font=f, fill=(255, 255, 255, a), stroke_width=4, stroke_fill=(0, 0, 0, int(a * 0.9)))
        if tx.get("sub"):
            f2 = font("en", 30); bb = d.textbbox((0, 0), tx["sub"], font=f2)
            d.text((W / 2 - (bb[2] - bb[0]) / 2, y + (full[3] - full[1]) + 26), tx["sub"], font=f2, fill=(220, 224, 232, a), stroke_width=2, stroke_fill=(0, 0, 0, a))
    elif st == "title":
        sc = 1 + 0.25 * (1 - ease(u / 0.25, "snap"))
        f = font("zhb", int(tx.get("size", 170) * sc)); bb = d.textbbox((0, 0), tx["big"], font=f)
        y = H * tx.get("y", 0.36) - (bb[3] - bb[1]) / 2
        d.text((W / 2 - (bb[2] - bb[0]) / 2, y), tx["big"], font=f, fill=lc + (255,), stroke_width=6, stroke_fill=dc + (255,))
        if tx.get("sub"):
            f2 = font("en", 46); b2 = d.textbbox((0, 0), tx["sub"], font=f2)
            d.text((W / 2 - (b2[2] - b2[0]) / 2, y + (bb[3] - bb[1]) + 60), tx["sub"], font=f2, fill=lc + (255,), stroke_width=2, stroke_fill=dc + (255,))
    elif st == "card":  # 小字說明，左下
        a = int(255 * min(1, u / 0.3))
        d.text((90, H * 0.86), tx["big"], font=font("zh", 38), fill=(250, 248, 240, a), stroke_width=3, stroke_fill=(0, 0, 0, a))
    return fr

# ---------------- 一格 ----------------
def layer(s, lt, gt):
    dur = s["t1"] - s["t0"]; fac = s.get("fac", "mono")
    bg = s.get("bg", ("col", (0, 0, 0)))
    if bg[0] == "card":
        fr = card(bg[1], bg[2], gt, s.get("seed", 0))
    elif bg[0] == "img":
        f0 = bg[2]; f1 = bg[3] if len(bg) > 3 and bg[3] else f0
        fr = img_bg(bg[1], lerp(f0, f1, ease(lt / dur, s.get("bease", "lin"))), s.get("bflip", False))
        if s.get("grade"): fr = duotone(fr, s["grade"][0], s["grade"][1])
    elif bg[0] == "map":
        m = bg[1]
        if "f1" in m: m = dict(m, f=lerp(m["f"], m["f1"], ease(lt / dur, m.get("ease", "out"))))
        fr = map_frame(m, lt)
    else:
        fr = Image.new("RGB", (W, H), bg[1])
    if s.get("tex"):  # 色卡上疊一層淡淡的場景
        tx = duotone(img_bg(s["tex"][0], (0.5, 0.5, 1.0 + 0.05 * lt / dur)), s["tex"][1])
        fr = ImageChops.multiply(fr, Image.blend(Image.new("RGB", (W, H), (255, 255, 255)), tx, s["tex"][2])) if s["tex"][3] == "mul" else Image.blend(fr, tx, s["tex"][2])
    for kind in s.get("under", []):
        fr = vfx(fr, kind[0], gt, kind[1], s.get("seed", 0), kind[2] if len(kind) > 2 else None)
    for c in s.get("ch", []):
        fr = draw_char(fr, c, lt, dur, fac)
    return fr

def frame(s, lt, amb):
    gt = s["t0"] + lt
    if "split" in s:
        sp = s["split"]
        a = layer(dict(sp["a"], t0=s["t0"], t1=s["t1"]), lt, gt)
        b = layer(dict(sp["b"], t0=s["t0"], t1=s["t1"]), lt, gt)
        y, x = _YX
        tilt = sp.get("tilt", 0.35)
        slide = sp.get("slide", 0.0) * (1 - ease(lt / 0.3, "snap"))
        u = (x - W * (0.5 + slide)) - (y - H * 0.5) * tilt
        m = Image.fromarray(((u > 0) * 255).astype(np.uint8))
        fr = Image.composite(b, a, m)
        ln = Image.fromarray(((np.abs(u) < 9) * 255).astype(np.uint8))
        fr.paste((255, 255, 255), (0, 0), ln)
    else:
        fr = layer(s, lt, gt)
    for a in amb:
        if a[0] <= gt < a[1] and not s.get("noamb"):
            fr = vfx(fr, a[2], gt, a[3], int(a[0]), a[4] if len(a) > 4 else None)
    for kind in s.get("vfx", []):
        fr = vfx(fr, kind[0], gt, kind[1], s.get("seed", 0), kind[2] if len(kind) > 2 else None)
    fr = events(fr, s, lt)
    for tx in s.get("txt", []):
        fr = text(fr, tx, lt, s.get("fac", "mono"))
    return finish(fr, gt)

_CURVE = [int(min(255, 255 * (max(0.0, (v / 255 - 0.04) / 0.94) ** 1.06))) for v in range(256)] * 3
_yy, _xx = np.mgrid[0:H, 0:W]
VIG = np.clip(1 - 0.42 * np.clip(np.sqrt(((_xx - W / 2) / (W / 2)) ** 2 + ((_yy - H / 2) / (H / 2)) ** 2) - 0.6, 0, 1) ** 1.5, 0, 1).astype(np.float32)[..., None]
del _yy, _xx
_g = RNG(3)
GRAIN = [(_g.standard_normal((H // 2, W // 2)).astype(np.float32) * 7) for _ in range(5)]
def finish(fr, gt):
    a = np.asarray(fr.point(_CURVE)).astype(np.float32) * VIG
    g = GRAIN[int(gt * FPS) % 5]
    a += np.repeat(np.repeat(g, 2, 0), 2, 1)[..., None]
    return Image.fromarray(a.clip(0, 255).astype(np.uint8))

# ---------------- 主程式 ----------------
def load_edl():
    sp = importlib.util.spec_from_file_location("edl2", os.environ.get("EDL2", f"{ROOT}/60_cut/edl2.py"))
    m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
    return m.SHOTS, getattr(m, "AMB", [])

def shot_at(shots, t):
    lo, hi = 0, len(shots) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if shots[mid]["t0"] <= t: lo = mid
        else: hi = mid - 1
    return shots[lo]

def main():
    args = sys.argv[1:]; out = f"{ROOT}/60_cut/out2.mp4"; frames = None
    if "--out" in args: i = args.index("--out"); out = args[i + 1]; del args[i:i + 2]
    if "--frames" in args: i = args.index("--frames"); frames = [float(x) for x in args[i + 1].split(",")]; del args[i:i + 2]
    shots, amb = load_edl(); end = shots[-1]["t1"]
    t0, t1 = (float(args[0]), float(args[1])) if args else (0, end)
    if frames:
        os.makedirs(f"{ROOT}/60_cut/frames2", exist_ok=True)
        for t in frames:
            s = shot_at(shots, t); frame(s, t - s["t0"], amb).save(f"{ROOT}/60_cut/frames2/f_{t:07.2f}.jpg", quality=88)
        return
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    import time; st = time.time()
    n0, n1 = int(round(t0 * FPS)), int(round(t1 * FPS))
    for n in range(n0, n1):
        t = n / FPS; s = shot_at(shots, t)
        p.stdin.write(frame(s, t - s["t0"], amb).tobytes())
        if (n - n0) % 240 == 0: print(f"{t:7.2f}s {(time.time()-st)/(n-n0+1):.3f}s/格", flush=True)
    p.stdin.close(); p.wait(); print("done", out, f"{time.time()-st:.0f}s")

if __name__ == "__main__":
    main()
