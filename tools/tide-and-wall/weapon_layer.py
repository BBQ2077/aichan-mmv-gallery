"""原圖 + Muse「只拿掉武器」版 → 原位置的 body / weapon 兩個 RGBA 圖層與握點。
用法：weapon_layer.py 原圖.png 去武器.png 輸出資料夾
"""
import sys, os, json
import numpy as np
from PIL import Image, ImageFilter

def gmask(im):
    a = np.asarray(im.convert('RGB')).astype(np.int16)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    green = (g > 140) & (g - r > 60) & (g - b > 60)
    return ~green

def rgba(im, m):
    a = np.asarray(im.convert('RGB')).copy()
    a[..., 1] = np.minimum(a[..., 1], np.maximum(a[..., 0], a[..., 2]).astype(np.int16) + 20).astype(np.uint8)  # 去綠邊
    al = Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8))
    o = Image.fromarray(a).convert('RGBA'); o.putalpha(al); return o

def place(im, s, tx, ty, W, H):
    w, h = max(1, round(im.width * s)), max(1, round(im.height * s))
    c = Image.new(im.mode, (W, H), (0, 255, 0) if im.mode == 'RGB' else 0)
    c.paste(im.resize((w, h), Image.LANCZOS), (round(tx), round(ty)))
    return c

def main(orig_p, nw_p, out):
    os.makedirs(out, exist_ok=True)
    O = Image.open(orig_p).convert('RGB'); N = Image.open(nw_p).convert('RGB')
    W, H = O.size; mo = gmask(O); mn = gmask(N)
    # 粗估：用垂直範圍推比例，再小範圍格點搜尋（縮 1/4 計算）
    k = 4
    mo_s = mo[::k, ::k]
    ys, xs = np.nonzero(mn); yo, xo = np.nonzero(mo)
    same_ratio = abs(W / H - N.width / N.height) < 0.02
    s0 = W / N.width if same_ratio else (yo.max() - yo.min()) / max(1, ys.max() - ys.min())
    span = 0.03 if same_ratio else 0.1
    best = None
    Nm = Image.fromarray((mn * 255).astype(np.uint8))
    for s in np.linspace(s0 * (1 - span), s0 * (1 + span), 13 if same_ratio else 21):
        sm = np.asarray(Nm.resize((max(1, round(N.width * s / k)), max(1, round(N.height * s / k))))) > 127
        sy, sx = np.nonzero(sm)
        ty0 = 0 if same_ratio else yo.min() / k - sy.min()
        txr = range(-8, 9, 1) if same_ratio else range(-sm.shape[1], mo_s.shape[1], 2)
        for ty in range(int(ty0) - 6, int(ty0) + 7, 1):
            for tx in txr:
                c = np.zeros_like(mo_s)
                y1, x1 = max(0, ty), max(0, tx)
                y2, x2 = min(c.shape[0], ty + sm.shape[0]), min(c.shape[1], tx + sm.shape[1])
                if y2 <= y1 or x2 <= x1: continue
                c[y1:y2, x1:x2] = sm[y1 - ty:y2 - ty, x1 - tx:x2 - tx]
                sc = (c & mo_s).sum() - 3 * (c & ~mo_s).sum()
                if best is None or sc > best[0]: best = (sc, s, tx * k, ty * k)
    _, s, tx, ty = best
    # 細調 ±k 像素
    fine = None
    for dx in range(-k, k + 1):
        for dy in range(-k, k + 1):
            c = np.asarray(place(Nm, s, tx + dx, ty + dy, W, H)) > 127
            sc = (c & mo).sum() - 3 * (c & ~mo).sum()
            if fine is None or sc > fine[0]: fine = (sc, dx, dy, c)
    _, dx, dy, mb = fine; tx += dx; ty += dy
    body = place(N, s, tx, ty, W, H)
    mb = gmask(body)
    mb_d = np.asarray(Image.fromarray((mb * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(7))) > 127
    mw = mo & ~mb_d
    # 只留最大連通區附近（去掉頭髮邊緣雜點）：簡化為移除小於 0.3% 面積的列塊
    from collections import deque
    lab = np.zeros(mw.shape, np.int32); n = 0; sizes = {}
    for y0, x0 in zip(*np.nonzero(mw)):
        if lab[y0, x0]: continue
        n += 1; q = deque([(y0, x0)]); lab[y0, x0] = n; cnt = 0
        while q:
            y, x = q.popleft(); cnt += 1
            for yy, xx in ((y+1,x),(y-1,x),(y,x+1),(y,x-1)):
                if 0 <= yy < H and 0 <= xx < W and mw[yy, xx] and not lab[yy, xx]:
                    lab[yy, xx] = n; q.append((yy, xx))
        sizes[n] = cnt
    keep = [i for i, c in sizes.items() if c > 0.003 * W * H]
    mw = np.isin(lab, keep)
    # 握點：武器遮罩中最靠近身體遮罩的點群中心
    near = mw & (np.asarray(Image.fromarray((mb * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(15))) > 127)
    gy, gx = np.nonzero(near if near.any() else mw)
    grip = [int(gx.mean()), int(gy.mean())]
    rgba(body, mb).save(f'{out}/body.png')
    rgba(O, mw).save(f'{out}/weapon.png')
    chk = Image.new('RGB', (W * 2, H), (40, 40, 40))
    chk.paste(O, (0, 0))
    comp = Image.new('RGBA', (W, H), (40, 40, 40, 255))
    comp.alpha_composite(Image.open(f'{out}/body.png')); comp.alpha_composite(Image.open(f'{out}/weapon.png'))
    chk.paste(comp.convert('RGB'), (W, 0))
    from PIL import ImageDraw
    d = ImageDraw.Draw(chk); d.ellipse([W + grip[0] - 8, grip[1] - 8, W + grip[0] + 8, grip[1] + 8], outline='red', width=3)
    chk.save(f'{out}/check.jpg', quality=88)
    json.dump({'size': [W, H], 'body_scale': round(float(s), 4), 'body_xy': [int(tx), int(ty)],
               'grip': grip, 'weapon_px': int(mw.sum())}, open(f'{out}/rig.json', 'w'), indent=1)
    print('scale', round(float(s), 3), 'xy', int(tx), int(ty), 'grip', grip, 'weapon px', int(mw.sum()), 'comps kept', len(keep))

if __name__ == '__main__':
    main(*sys.argv[1:4])
