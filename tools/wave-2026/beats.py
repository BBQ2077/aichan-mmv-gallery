"""量節拍：用 ABC 的 BPM 建格線，再用實際音訊的起音包絡找相位與每拍強度。
用法：python beats.py song.json  → 同名 _beats.json
輸出：bpm、offset、beats[{t, bar, k(小節內第幾拍), on(全頻起音強度 0..1), lo(低頻), hi(高頻), sec}]、sections"""
import sys, json, subprocess, re
import numpy as np

js = sys.argv[1]; mp3 = js.replace('.json', '.mp3')
import os
tmp = js.replace('.json', '_info.json')
subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'song_info.py'), js, '--json', tmp], capture_output=True)
_i = json.load(open(tmp))
_se = _i['sections']
info = dict(bpm=_i['bpm'], phrases=_i['phrases'],
            sections=[dict(name=n, t0=a, t1=(_se[k + 1][1] if k + 1 < len(_se) else 9999)) for k, (n, a) in enumerate(_se)])
SR = 22050; HOP = 256
raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', mp3, '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'], capture_output=True).stdout
x = np.frombuffer(raw, np.float32)
N = 2048; nfr = (len(x) - N) // HOP
win = np.hanning(N).astype(np.float32)
S = np.empty((nfr, N // 2 + 1), np.float32)
for i in range(0, nfr, 4096):
    j = min(nfr, i + 4096)
    idx = np.arange(i, j)[:, None] * HOP + np.arange(N)[None]
    S[i:j] = np.abs(np.fft.rfft(x[idx] * win, axis=1))
L = np.log1p(S * 10)
fq = np.fft.rfftfreq(N, 1 / SR)
def flux(lo, hi):
    m = (fq >= lo) & (fq < hi)
    d = np.diff(L[:, m], axis=0); d[d < 0] = 0
    e = np.concatenate([[0], d.sum(1)])
    return e / (np.percentile(e, 99) + 1e-9)
on, low, high = flux(30, 8000), flux(30, 150), flux(3000, 10000)
ft = np.arange(nfr) * HOP / SR

bpm = info['bpm']; bt = 60 / bpm; dur = len(x) / SR
# 相位：offset 0..bt 掃描，讓拍點上的起音最大
def score(off):
    ts = np.arange(off, dur, bt); ii = np.clip((ts * SR / HOP).astype(int), 0, nfr - 1)
    return on[ii].sum() + low[ii].sum()
offs = np.linspace(0, bt, 200, endpoint=False); sc = [score(o) for o in offs]
off = offs[int(np.argmax(sc))]
# 下拍：每 4 拍中哪個相位低頻最強
ts = np.arange(off, dur, bt)
def pk(env, t, w=0.05):
    a, b = int((t - w) * SR / HOP), int((t + w) * SR / HOP)
    seg = env[max(a, 0):max(b, 1)]
    return float(seg.max()) if len(seg) else 0.0
lo_ = np.array([pk(low, t) for t in ts])
ph = int(np.argmax([lo_[k::4].sum() for k in range(4)]))
# 讓 ABC 段落對齊：段落起點吸到最近下拍
secs = [(s['name'], s['t0'], s['t1']) for s in info['sections']]
beats = []
for i, t in enumerate(ts):
    k = (i - ph) % 4; bar = (i - ph) // 4
    sec = next((n for n, a, b in secs if a - 0.2 <= t < b - 0.2), secs[-1][0])
    beats.append(dict(t=round(float(t), 4), bar=int(bar), k=int(k), on=round(pk(on, t), 3), lo=round(float(lo_[i]), 3),
                      hi=round(pk(high, t), 3), sec=sec))
out = dict(bpm=bpm, beat=bt, phrases=info['phrases'], offset=round(float(off), 4), downphase=ph, dur=dur, sections=secs, beats=beats,
           phase_score=round(max(sc) / np.mean(sc), 3))
json.dump(out, open(js.replace('.json', '_beats.json'), 'w'), indent=0)
print(f'bpm {bpm} offset {off:.3f}s downphase {ph} phase_contrast {max(sc) / np.mean(sc):.2f} beats {len(beats)}')
# 每小節強度列印
for s, a, b in secs:
    bb = [x_ for x_ in beats if a - 0.2 <= x_['t'] < b - 0.2]
    if bb: print(f'{s:11s} {a:6.1f}-{b:6.1f} on {np.mean([q["on"] for q in bb]):.2f} lo {np.mean([q["lo"] for q in bb]):.2f} hi {np.mean([q["hi"] for q in bb]):.2f}')
