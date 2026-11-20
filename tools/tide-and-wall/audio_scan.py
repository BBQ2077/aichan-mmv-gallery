"""音軌快篩：長度、每 2 秒 RMS 曲線、整體響度；輸出比較圖。
用法：audio_scan.py out.png a.mp3 b.mp3 ...
"""
import subprocess, sys, re, json
from PIL import Image, ImageDraw, ImageFont


def rms_curve(path, win=2.0):
    cmd = ['ffmpeg', '-hide_banner', '-i', path, '-af',
           f'aresample=8000,asetnsamples=n={int(8000*win)},astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level',
           '-f', 'null', '-']
    out = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore').stderr
    v = [float(x) if x not in ('-inf',) else -90.0 for x in re.findall(r'RMS_level=(-?[\d.]+|-inf)', out)]
    return v


def loud(path):
    out = subprocess.run(['ffmpeg', '-hide_banner', '-i', path, '-af', 'ebur128', '-f', 'null', '-'],
                         capture_output=True, text=True, encoding='utf-8', errors='ignore').stderr
    m = re.findall(r'I:\s+(-?[\d.]+) LUFS', out)
    return float(m[-1]) if m else None


files = sys.argv[2:]
W, H, PAD = 1600, 140, 30
img = Image.new('RGB', (W, PAD + H * len(files)), 'white'); d = ImageDraw.Draw(img)
# 劇情時間標記
marks = [(20, '高牆'), (55, '鍛造'), (75, '潮起'), (110, '棋局'), (145, '談判'), (155, '赤原'), (185, '灰燼'), (220, '破城'), (260, '書庫'), (290, '新王'), (320, 'END')]
font = ImageFont.truetype('C:/Windows/Fonts/msjh.ttc', 14)
T = 380.0
for t, n in marks:
    x = int(t / T * W); d.line([(x, PAD - 5), (x, img.height)], fill=(220, 220, 220)); d.text((x + 2, 5), n, fill=(120, 120, 120), font=font)
res = {}
for i, f in enumerate(files):
    v = rms_curve(f); dur = len(v) * 2.0; L = loud(f)
    y0 = PAD + i * H
    pts = [(int(k * 2.0 / T * W), y0 + H - 10 - int(max(0, (x + 45)) / 40 * (H - 20))) for k, x in enumerate(v)]
    if len(pts) > 1: d.line(pts, fill=(30, 60, 160), width=2)
    d.text((5, y0 + 5), f'{f.split("/")[-1]}  {dur:.0f}s  {L} LUFS', fill='black', font=font)
    res[f] = {'dur': dur, 'lufs': L, 'rms10': [round(sum(v[k:k+5]) / len(v[k:k+5]), 1) for k in range(0, len(v), 5)]}
img.save(sys.argv[1])
print(json.dumps(res, ensure_ascii=False))
