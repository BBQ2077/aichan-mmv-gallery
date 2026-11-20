"""Muse 圖 RealESRGAN anime x4 → 縮成 2 倍，存 10_img/muse_x2/（局部切鏡用）"""
import os, sys, glob, subprocess
from PIL import Image
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
UP = 'C:/Users/user/hermes-files/ai-war-mmv/_tools/upscale.py'
os.makedirs(R + '/10_img/muse_x2', exist_ok=True)
tmp = R + '/_jobs/up_tmp.png'
for f in sorted(glob.glob(R + '/10_img/muse/*.png')):
    out = R + '/10_img/muse_x2/' + os.path.basename(f)
    if os.path.exists(out): continue
    r = subprocess.run([PY, UP, f, tmp], capture_output=True, text=True, errors='replace')
    if not os.path.exists(tmp): print('FAIL', f, r.stdout[-300:], flush=True); continue
    im = Image.open(tmp).convert('RGB'); src = Image.open(f)
    im.resize((src.width * 2, src.height * 2), Image.LANCZOS).save(out)
    os.remove(tmp); print('ok', os.path.basename(f), flush=True)
