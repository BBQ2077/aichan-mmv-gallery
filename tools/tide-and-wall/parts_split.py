"""分件圖切割：綠底分件圖 → 依連通區塊切出部件（由左到右＝head, body, cape, weapon）→ 各自 RGBA；
再把每個部件在原姿勢圖上做縮放＋平移搜尋（灰階 SAD），求出貼回位置，寫 rig.json 給 fx.py 用。
用法：python _tools/parts_split.py parts.png pose.png outdir"""
import sys, os, json
import numpy as np
from PIL import Image
NAMES = ['head', 'body', 'cape', 'weapon']


def key(im):
    a = np.asarray(im.convert('RGB')).astype(int)
    g = (a[..., 1] > 140) & (a[..., 1] - np.maximum(a[..., 0], a[..., 2]) > 60)
    return ~g


def components(mask, step=4):
    m = mask[::step, ::step]; lab = np.zeros(m.shape, int); n = 0; H, W = m.shape
    for y in range(H):
        for x in range(W):
            if m[y, x] and not lab[y, x]:
                n += 1; st = [(y, x)]; lab[y, x] = n
                while st:
                    cy, cx = st.pop()
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
                        yy, xx = cy + dy, cx + dx
                        if 0 <= yy < H and 0 <= xx < W and m[yy, xx] and not lab[yy, xx]:
                            lab[yy, xx] = n; st.append((yy, xx))
    out = []
    for i in range(1, n + 1):
        ys, xs = np.nonzero(lab == i)
        if len(ys) < 200: continue  # 雜點
        out.append((xs.min() * step, ys.min() * step, (xs.max() + 1) * step, (ys.max() + 1) * step, len(ys)))
    return sorted(out, key=lambda b: b[0])


def locate(part_rgba, pose_gray, pose_mask, scales=np.arange(0.6, 1.41, 0.05), ymax=1.0):
    """粗到細：在原姿勢圖上搜尋縮放 0.6～1.4 與位置，最小化有效像素的灰階差。"""
    pa = np.asarray(part_rgba); best = None
    for sc in scales:
        w, h = int(pa.shape[1] * sc / 4), int(pa.shape[0] * sc / 4)
        if w < 4 or h < 4 or w >= pose_gray.shape[1] or h >= pose_gray.shape[0]: continue
        p = Image.fromarray(pa).resize((w, h)); g = np.asarray(p.convert('L')).astype(float); al = np.asarray(p)[..., 3] > 128
        if al.sum() < 20: continue
        for y in range(0, min(pose_gray.shape[0] - h, int(pose_gray.shape[0] * ymax)), 2):
            for x in range(0, pose_gray.shape[1] - w, 2):
                win = pose_gray[y:y + h, x:x + w]
                d = np.abs(win - g)[al].mean() + 40 * (1 - pose_mask[y:y + h, x:x + w][al].mean())
                if best is None or d < best[0]: best = (d, sc, x * 4, y * 4)
    return best


if __name__ == '__main__':
    parts_p, pose_p, outd = sys.argv[1:4]; os.makedirs(outd, exist_ok=True)
    P = Image.open(parts_p).convert('RGB'); M = key(P)
    comps = components(M)
    # 水平範圍重疊過半的區塊視為同一部件（例：腿與身體上下分開）
    comps = sorted(comps, key=lambda b: b[0]); merged = []
    for c in comps:
        for i, m in enumerate(merged):
            ov = min(c[2], m[2]) - max(c[0], m[0])
            if ov > 0.5 * min(c[2] - c[0], m[2] - m[0]):
                merged[i] = (min(c[0], m[0]), min(c[1], m[1]), max(c[2], m[2]), max(c[3], m[3]), c[4] + m[4]); break
        else: merged.append(c)
    comps = sorted(sorted(merged, key=lambda b: -b[4])[:4], key=lambda b: b[0])
    pose = Image.open(pose_p).convert('RGB'); pm = key(pose)
    sm = pose.resize((pose.width // 4, pose.height // 4))
    pg = np.asarray(sm.convert('L')).astype(float); pmask = np.asarray(Image.fromarray(pm).resize(sm.size)).astype(float)
    rig = {'pose': pose_p, 'size': pose.size, 'parts': {}}
    boxes = dict(zip(NAMES, comps)); sb = None
    # 先找身體（最大、最穩）：寬範圍縮放；其他部件共用同一比例 ±15%（分件圖照原圖比例生成）
    for name in ['body', 'cape', 'weapon', 'head']:
        if name not in boxes: continue
        x0, y0, x1, y1, _ = boxes[name]
        crop = P.crop((x0, y0, x1, y1)); a = Image.fromarray((M[y0:y1, x0:x1] * 255).astype('uint8'))
        rgba = crop.convert('RGBA'); rgba.putalpha(a); rgba.save(f'{outd}/{name}.png')
        if sb is None:  # 面積比估整體比例（部件補完被擋處，總面積略大於原圖人物）
            s0 = (pm.sum() / M.sum()) ** 0.5; print('s0', round(float(s0), 3))
            kw = {'scales': np.arange(s0 * 0.9, s0 * 1.351, s0 * 0.05)}
        else: kw = {'scales': np.arange(sb * 0.9, sb * 1.101, sb * 0.025)}
        if name == 'head': kw['ymax'] = 0.45
        d, sc, x, y = locate(rgba, pg, pmask, **kw)
        if name == 'body':  # 細搜
            d, sc, x, y = locate(rgba, pg, pmask, scales=np.arange(sc * 0.96, sc * 1.041, sc * 0.02)); sb = sc
        rig['parts'][name] = {'file': f'{outd}/{name}.png', 'scale': round(float(sc), 3), 'x': int(x), 'y': int(y), 'err': round(float(d), 1)}
        print(name, rig['parts'][name])
    json.dump(rig, open(f'{outd}/rig.json', 'w'), indent=1)
    # 對照圖：左原圖、右部件貼回（cape→body→weapon→head）
    cv = Image.new('RGBA', pose.size, (0, 255, 0, 255))
    for name in ['cape', 'body', 'weapon', 'head']:
        r = rig['parts'].get(name)
        if not r: continue
        im = Image.open(r['file']); im = im.resize((int(im.width * r['scale']), int(im.height * r['scale'])))
        cv.alpha_composite(im, (r['x'], r['y']))
    ck = Image.new('RGB', (pose.width * 2, pose.height)); ck.paste(pose, (0, 0)); ck.paste(cv.convert('RGB'), (pose.width, 0)); ck.save(f'{outd}/check.jpg', quality=85)
