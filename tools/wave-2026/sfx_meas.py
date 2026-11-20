"""量音效：時長、峰值位置、起音時間、頻段重心、低頻比例、尾音長度、響度 → 20_audio/sfx/meas.tsv"""
import glob, os, subprocess, sys
import numpy as np
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
names = {l.split('\t')[0]: l.split('\t')[2].strip() for l in open(R + '/20_audio/sfx/mk_list.tsv', encoding='utf-8')}
SR = 44100
rows = []
for f in sorted(glob.glob(R + '/20_audio/sfx/mk/*')):
    if f.endswith('.wav') and os.path.getsize(f) < 10000: continue
    x = np.frombuffer(subprocess.run(['ffmpeg', '-v', 'error', '-i', f, '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'], capture_output=True).stdout, np.float32)
    if len(x) < 1000: continue
    hop = 441; env = np.sqrt(np.convolve(x ** 2, np.ones(hop) / hop, 'same')[::hop] + 1e-12); db = 20 * np.log10(env + 1e-9)
    pk = int(np.argmax(env)); pdb = db[pk]
    st = int(np.argmax(db > pdb - 20)); tail = len(db) - 1 - int(np.argmax(db[::-1] > pdb - 30))
    seg = x[max(0, pk * hop - 2205): pk * hop + 22050]
    sp = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))) ** 2; fq = np.fft.rfftfreq(len(seg), 1 / SR)
    cen = float((sp * fq).sum() / sp.sum()); low = float(sp[fq < 120].sum() / sp.sum())
    rows.append((os.path.basename(f).split('.')[0], len(x) / SR, pk * hop / SR, (pk - st) * hop / SR, cen, low, (tail - pk) * hop / SR, pdb,
                 names.get(os.path.basename(f).split('.')[0], '')))
with open(R + '/20_audio/sfx/meas.tsv', 'w', encoding='utf-8') as o:
    o.write('id\tdur\tpeak_t\tattack\tcentroid\tlow120\ttail\tpeak_db\tname\n')
    for r in sorted(rows, key=lambda r: r[4]):
        o.write('\t'.join(f'{v:.2f}' if isinstance(v, float) else str(v) for v in r) + '\n')
        print(f'{r[0]:>5} dur{r[1]:5.1f} pk@{r[2]:4.2f} atk{r[3]:4.2f} cen{r[4]:6.0f} low{r[5]:4.2f} tail{r[6]:4.1f} {r[7]:5.1f}dB  {r[8]}')
