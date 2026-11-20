"""相鄰格相位相關：全域位移 dx,dy 與峰值。找來回震盪（位移方向反覆變號）的秒數。"""
import sys, subprocess, numpy as np
p = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", sys.argv[1], "-vf", "scale=320:180,format=gray", "-f", "rawvideo", "-"], capture_output=True)
a = np.frombuffer(p.stdout, np.uint8).reshape(-1, 180, 320).astype(np.float32)
win = np.outer(np.hanning(180), np.hanning(320))
F = [np.fft.fft2((f - f.mean()) * win) for f in a]
res = []
for i in range(1, len(a)):
    R = F[i] * np.conj(F[i - 1]); R /= np.abs(R) + 1e-6
    c = np.real(np.fft.ifft2(R)); k = np.unravel_index(np.argmax(c), c.shape)
    dy, dx = k[0] if k[0] < 90 else k[0] - 180, k[1] if k[1] < 160 else k[1] - 320
    res.append((dx, dy, c.max()))
res = np.array(res, np.float32); np.save(sys.argv[1] + ".shift.npy", res)
fps = 24; out = []
for s in range(len(res) // fps):
    r = res[s * fps:(s + 1) * fps]; ok = r[:, 2] > 0.08
    m = np.hypot(r[:, 0], r[:, 1]) * ok
    sx = np.sign(r[:, 0] * ok); sy = np.sign(r[:, 1] * ok)
    flips = int(((sx[1:] * sx[:-1]) < 0).sum() + ((sy[1:] * sy[:-1]) < 0).sum())
    big = int((m >= 2).sum())
    if flips >= 4 and big >= 3: out.append((s, flips, big, round(float(m.max()), 1)))
print("秒, 變號次數, 位移>=2px(320寬)格數, 最大位移"); print(out)
