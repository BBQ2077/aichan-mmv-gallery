"""YuE2 候選分析：ABC 譜 → 段落時間、人聲樂句；音訊 → 每段響度、節拍。
用法：python song_info.py cand/song_x_1.json [--json out.json]"""
import json, re, sys, subprocess, pathlib
import numpy as np
from fractions import Fraction

src = pathlib.Path(sys.argv[1]); j = json.loads(src.read_text(encoding='utf-8'))
abc = j['abc']
bpm = int(re.search(r'Q:1/4=(\d+)', abc).group(1))
L = Fraction(re.search(r'L:(\d+)/(\d+)', abc).group(0)[2:])
M = re.search(r'M:(\d+)/(\d+)', abc).groups(); bar_q = Fraction(int(M[0]), int(M[1])) * 4  # 每小節幾個四分音符
spb = 60 / bpm; bar_s = float(bar_q) * spb


def dur_tokens(body):
    """回傳一小節內 (是否休止, 長度[L單位]) 序列"""
    body = re.sub(r'"[^"]*"', '', body)
    out = []
    for m in re.finditer(r"(z|[A-Ga-g][,']*)(\d*)(/?\d*)", body):
        n = int(m.group(2)) if m.group(2) else 1
        out.append((m.group(1) == 'z', n))
    return out


sec = []; cur = None; voice = None; t = 0.0; vt = 0.0; phrases = []; ph_start = None
lines = abc.split('\n')
for ln in lines:
    s = ln.strip()
    if s.startswith('%'):
        cur = s[1:].strip(); sec.append([cur, t]); continue
    if s.startswith('V:'):
        voice = 'Vocal' if 'Vocal' in s else 'Ins'; continue
    if voice != 'Vocal' or not s or s[0].isalpha() and s[1:2] == ':':
        continue
    for bar in [b for b in s.split('|') if b.strip()]:
        b = bar.strip()
        if b.startswith('Z'):
            k = int(b[1:] or 1); t += k * bar_s
            if ph_start is not None: phrases.append((ph_start, t - k * bar_s, cur)); ph_start = None
            continue
        pos = t
        for rest, n in dur_tokens(b):
            d = float(n * L * 4) * spb
            if rest:
                if ph_start is not None and d >= spb * 0.99: phrases.append((ph_start, pos, cur)); ph_start = None
            else:
                if ph_start is None: ph_start = pos
            pos += d
        t += bar_s
if ph_start is not None: phrases.append((ph_start, t, cur))
# 音訊
mp3 = str(src).replace('.json', '.mp3')
x = np.frombuffer(subprocess.run(['ffmpeg', '-v', 'error', '-i', mp3, '-ac', '1', '-ar', '22050', '-f', 'f32le', '-'], capture_output=True).stdout, np.float32)
dur = len(x) / 22050
rms = np.array([np.sqrt(np.mean(x[i * 22050:(i + 1) * 22050] ** 2) + 1e-12) for i in range(int(dur))])
db = 20 * np.log10(rms + 1e-9)
print(f'{src.name}  bpm {bpm}  bar {bar_s:.3f}s  score_len {t:.1f}s  audio {dur:.1f}s')
for i, (n, st) in enumerate(sec):
    en = sec[i + 1][1] if i + 1 < len(sec) else t
    seg = db[int(st):max(int(st) + 1, int(en))]
    print(f'  {n:10s} {st:6.1f}-{en:6.1f} ({(en - st) / bar_s:4.0f} bars)  loud {seg.mean():6.1f} dB  max {seg.max():6.1f}')
merged = []
for a, b, c in phrases:
    if merged and a - merged[-1][1] < spb * 0.6 and merged[-1][2] == c: merged[-1][1] = b
    else: merged.append([a, b, c])
print('  vocal phrases:', len(merged))
for a, b, c in merged: print(f'    {a:6.1f}-{b:6.1f} {c}')
if '--json' in sys.argv:
    json.dump({'bpm': bpm, 'bar': bar_s, 'sections': sec, 'phrases': merged, 'dur': dur, 'db': db.round(1).tolist()},
              open(sys.argv[sys.argv.index('--json') + 1], 'w'), indent=1)
