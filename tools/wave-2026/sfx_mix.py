"""音效三層＋混音。讀 edl 的 SFX=[(t, 層級或id, dB, opts)]，音樂為主：
S 小（短 whoosh，-21 dB）、M 中（whoosh-hit／低頻短擊，-15 dB）、L 大（電影重擊，-10 dB，音樂讓位 -4 dB）
每層素材輪流不連續重複，音高 ±4%、音量 ±1.5 dB 隨機；樣本峰值對齊到 t。
用法：python sfx_mix.py out.wav [--nomusic]"""
import os, sys, json, subprocess, random, importlib.util
import numpy as np
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location('edl', R + '/60_cut/' + os.environ.get('EDL', 'edl.py')); E = importlib.util.module_from_spec(spec); spec.loader.exec_module(E)
SR = 44100
POOL = {'S': [1464, 1461, 166, 1490, 1492, 1467, 2639, 175], 'M': [2903, 2919, 772, 2303, 1143, 2609, 2952, 563],
        'L': [2908, 2909, 2902, 788, 3057, 2900, 2599, 1686]}
GAIN = {'S': -21, 'M': -15, 'L': -10}
PRE = {'S': 0.6, 'M': 0.9, 'L': 1.0}
HP = {'S': 250, 'M': 50, 'L': 0}
meas = {l.split('\t')[0]: l.rstrip('\n').split('\t') for l in open(R + '/20_audio/sfx/meas.tsv', encoding='utf-8')}


def load(i, rate=1.0, hp=0):
    f = next((R + f'/20_audio/sfx/mk/{i}.{e}' for e in ('wav', 'mp3') if os.path.exists(R + f'/20_audio/sfx/mk/{i}.{e}') and os.path.getsize(R + f'/20_audio/sfx/mk/{i}.{e}') > 10000))
    af = f'asetrate={int(SR * rate)},aresample={SR}' + (f',highpass=f={hp}' if hp else '')
    x = np.frombuffer(subprocess.run(['ffmpeg', '-v', 'error', '-i', f, '-af', af, '-ac', '2', '-ar', str(SR), '-f', 'f32le', '-'], capture_output=True).stdout, np.float32).reshape(-1, 2)
    return x / (np.abs(x).max() + 1e-9) * 10 ** (-1 / 20)


def place(bus, x, t, peak, pre=None, dur=None, align='peak'):
    if align == 'peak':
        s0 = int(max(0.0, peak - (pre if pre is not None else peak)) * SR); start = t - (peak - s0 / SR)
    else:
        s0 = 0; start = t
    seg = x[s0:] if dur is None else x[s0:s0 + int(dur * SR)]
    if dur is not None:  # 尾端淡出
        n = min(len(seg), int(0.3 * SR)); seg = seg.copy(); seg[-n:] *= np.linspace(1, 0, n)[:, None]
    n = min(len(seg), int(0.004 * SR)); seg = seg.copy(); seg[:n] *= np.linspace(0, 1, n)[:, None]
    a = int(start * SR)
    if a < 0: seg = seg[-a:]; a = 0
    b = min(len(bus), a + len(seg)); bus[a:b] += seg[:b - a]


def main():
    out = sys.argv[1]; music = '--nomusic' not in sys.argv
    mus = np.frombuffer(subprocess.run(['ffmpeg', '-v', 'error', '-i', R + '/' + E.SONG + '.mp3', '-ac', '2', '-ar', str(SR), '-f', 'f32le', '-'],
                                       capture_output=True).stdout, np.float32).reshape(-1, 2).copy()
    N = len(mus); bus = np.zeros((N, 2), np.float32); duck = np.ones(N, np.float32)
    rnd = random.Random(7); last = {k: [] for k in POOL}; log = []
    for item in sorted(E.SFX, key=lambda r: r[0]):
        t, lvl, db = item[:3]; opt = item[3] if len(item) > 3 else {}
        rate = 1 + rnd.uniform(-0.04, 0.04); jit = rnd.uniform(-1.5, 1.5)
        if lvl in POOL:
            cands = [c for c in POOL[lvl] if c not in last[lvl][-3:]]; i = rnd.choice(cands); last[lvl].append(i)
            g = GAIN[lvl] + db + jit; x = load(i, rate, HP[lvl]); pk = float(meas[str(i)][2]) / rate
            place(bus, x * 10 ** (g / 20), t, pk, PRE[lvl])
            if lvl == 'L':
                a = int((t - 0.05) * SR); b = int((t + 0.7) * SR); r = int((t + 1.4) * SR)
                duck[max(a, 0):b] = np.minimum(duck[max(a, 0):b], 10 ** (-4 / 20))
                duck[b:r] = np.minimum(duck[b:r], np.linspace(10 ** (-4 / 20), 1, r - b))
        else:
            i = int(lvl); g = -12 + db; x = load(i, 1.0); pk = float(meas[str(i)][2])
            place(bus, x * 10 ** (g / 20), t, pk, opt.get('pre'), opt.get('dur'), opt.get('align', 'peak'))
        log.append(f'{t:7.2f} {lvl} {i} {g:+.1f}dB')
    sm = np.convolve(duck, np.ones(441) / 441, 'same').astype(np.float32)
    mix = (mus * sm[:, None] if music else 0) + bus
    fo = int(3.0 * SR); mix[-fo:] *= (np.cos(np.linspace(0, np.pi / 2, fo)) ** 1.5)[:, None]  # 曲尾硬切 → 3 秒淡出
    tmp = out.replace('.wav', '_raw.wav')
    import wave
    pcm = (np.clip(mix, -1, 1) * 32767).astype(np.int16)
    with wave.open(tmp, 'wb') as w: w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', tmp, '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11', '-ar', str(SR), out])
    open(out.replace('.wav', '_sfx.log'), 'w').write('\n'.join(log))
    print(out, len(log), 'sfx')


if __name__ == '__main__':
    main()
