"""全片相鄰格差：找持續抖動（非切點的連續高差值）。用法: jitter.py <mp4>"""
import sys, subprocess, numpy as np
p = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", sys.argv[1], "-vf", "scale=320:180,format=gray", "-f", "rawvideo", "-"], capture_output=True)
a = np.frombuffer(p.stdout, np.uint8).reshape(-1, 180, 320).astype(np.float32)
d = np.abs(np.diff(a, axis=0)).mean(axis=(1, 2))
print("frames", len(a), "median", np.median(d))
# 每秒：大於 12 的格數（排除單次切點）
fps = 24; bad = []
for s in range(0, len(d) // fps):
    seg = d[s * fps:(s + 1) * fps]; n = int((seg > 12).sum())
    if n >= 5: bad.append((s, n, round(float(seg.mean()), 1)))
print("秒, >12格數, 平均:"); print(bad)
np.save(sys.argv[1] + ".diff.npy", d)
