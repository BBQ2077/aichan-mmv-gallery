"""白底去背 v2：
1. 從邊框泛洪的近白區當背景；
2. 內部封閉白區（髮絲縫、手臂與身體間）若周圍一圈多是有色像素（頭髮、裙子）也當背景；周圍是白布的（圍裙亮部）保留；
3. alpha 內縮 2px＋羽化，邊緣色由內往外擴散，去掉白色描邊和白光暈。
用法：python cutout2.py out_dir in1.png ..."""
import sys, os
import numpy as np
from PIL import Image, ImageFilter
from collections import deque


def comps(mask):
    """4 連通標記（純 Python BFS，mask 已縮小）"""
    h, w = mask.shape; lab = np.zeros((h, w), np.int32); n = 0
    ys, xs = np.nonzero(mask)
    for y0, x0 in zip(ys, xs):
        if lab[y0, x0]: continue
        n += 1; lab[y0, x0] = n; q = deque([(y0, x0)])
        while q:
            y, x = q.popleft()
            for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= yy < h and 0 <= xx < w and mask[yy, xx] and not lab[yy, xx]:
                    lab[yy, xx] = n; q.append((yy, xx))
    return lab, n


def cut(p, thr=236):
    im = Image.open(p).convert('RGB'); a = np.asarray(im).astype(np.int16); h, w, _ = a.shape
    white = (a.min(2) >= thr) & ((a.max(2) - a.min(2)) < 18)
    s = 3; sw, sh = w // s, h // s
    ws = np.asarray(Image.fromarray((white * 255).astype(np.uint8)).resize((sw, sh), Image.BOX)) > 240
    lab, n = comps(ws)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    bg = np.isin(lab, list(border))
    # 內部白區：看外圈
    small = np.asarray(im.resize((sw, sh), Image.BOX)).astype(np.int16)
    r_, g_, b_ = small[..., 0], small[..., 1], small[..., 2]
    colored = (small.max(2) - small.min(2) > 40) | (small.max(2) < 150)
    skin = (r_ > 190) & (g_ > 150) & (b_ > 120) & (r_ > b_ + 12) & (r_ - g_ < 70)
    for k in range(1, n + 1):
        if k in border: continue
        m = lab == k; area = m.sum()
        if area < 6: continue
        ring = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5))) > 0
        ring &= ~m
        if ring.sum() and colored[ring].mean() > 0.6 and skin[ring].mean() < 0.05: bg |= m
    bgf = np.asarray(Image.fromarray((bg * 255).astype(np.uint8)).resize((w, h), Image.BILINEAR)) > 100
    bgf &= white
    al = Image.fromarray(((~bgf) * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1.0))
    # 邊緣色往外擴：用內縮更多的區域顏色做加權模糊
    inner = np.asarray(al.filter(ImageFilter.MinFilter(9))).astype(np.float32)[..., None] / 255
    rgb = a.astype(np.float32)
    num = np.asarray(Image.fromarray(np.clip(rgb * inner, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(4))).astype(np.float32)
    den = np.asarray(Image.fromarray((inner[..., 0] * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(4))).astype(np.float32)[..., None] / 255
    spread = num / np.maximum(den, 1e-3)
    band = (np.asarray(al).astype(np.float32)[..., None] / 255 > 0.02) & (inner < 0.99)
    out = np.where(band, spread, rgb)
    o = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).convert('RGBA'); o.putalpha(al)
    bb = al.point(lambda v: 255 if v > 20 else 0).getbbox()
    return o.crop(bb) if bb else o


if __name__ == '__main__':
    od = sys.argv[1]; os.makedirs(od, exist_ok=True)
    for p in sys.argv[2:]:
        o = cut(p); n = os.path.splitext(os.path.basename(p))[0]
        o.save(f'{od}/{n}.png'); print(n, o.size, flush=True)
