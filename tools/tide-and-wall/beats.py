"""節拍表：頻譜通量 onset → 自相關估 BPM → 對齊相位 → 重拍（每小節第一拍）＋每拍強度＋每秒 RMS。
用法：python beats.py in.mp3 out.json"""
import sys, json, subprocess
import numpy as np

src, out = sys.argv[1], sys.argv[2]
SR, HOP = 22050, 256
x = np.frombuffer(subprocess.run(['ffmpeg', '-v', 'error', '-i', src, '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'],
                                 capture_output=True).stdout, np.float32)
n = len(x) // HOP - 4
win = np.hanning(1024).astype(np.float32)
idx = np.arange(n)[:, None] * HOP + np.arange(1024)[None]
idx = np.minimum(idx, len(x) - 1)
S = np.log1p(np.abs(np.fft.rfft(x[idx] * win, axis=1)) * 10)
flux = np.maximum(np.diff(S, axis=0), 0)
low = flux[:, 1:20].sum(1); full = flux.sum(1)
on = full / (full.max() + 1e-9); onl = low / (low.max() + 1e-9)
fps = SR / HOP
# BPM：自相關，限 70～180
o = on - np.convolve(on, np.ones(64) / 64, 'same')
ac = np.correlate(o, o, 'full')[len(o) - 1:]
lags = np.arange(len(ac))
bmin, bmax = int(fps * 60 / 180), int(fps * 60 / 70)
lag = bmin + int(np.argmax(ac[bmin:bmax]))
period = lag / fps; bpm = 60 / period
# 相位：在一個週期內找總 onset 最大的偏移
best, ph = -1, 0
for p in range(lag):
    s = o[p::lag].sum()
    if s > best: best, ph = s, p
beats = np.arange(ph, len(on), lag)
# 微調每拍到 ±3 個 hop 內的 onset 峰
bt = []
for b in beats:
    a, c = max(0, b - 3), min(len(on), b + 4)
    bt.append(a + int(np.argmax(on[a:c])))
bt = np.array(bt)
strength = [float(on[b]) for b in bt]; lowst = [float(onl[b]) for b in bt]
# 重拍：4 拍一小節，選低頻總量最大的相位
bar = max(range(4), key=lambda k: sum(lowst[k::4]))
rms = [float(20 * np.log10(np.sqrt((x[i * SR:(i + 1) * SR] ** 2).mean()) + 1e-9)) for i in range(len(x) // SR)]
# 強 onset（打擊點候選）：局部最大且 > 0.45
pk = [i for i in range(2, len(on) - 2) if on[i] > 0.45 and on[i] == on[i - 2:i + 3].max()]
res = {'bpm': round(bpm, 2), 'period': round(period, 4), 'dur': round(len(x) / SR, 2),
       'beats': [round(b / fps, 3) for b in bt], 'strength': [round(s, 3) for s in strength],
       'downbeats': [round(b / fps, 3) for b in bt[bar::4]], 'hits': [round(i / fps, 3) for i in pk], 'rms1s': [round(r, 1) for r in rms]}
json.dump(res, open(out, 'w'), indent=0)
print('bpm', res['bpm'], 'beats', len(bt), 'downbeats', len(res['downbeats']), 'hits', len(pk))
