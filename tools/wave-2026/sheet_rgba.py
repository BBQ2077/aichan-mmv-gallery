"""透明圖總覽（深藍底，看去背品質）。用法：python sheet_rgba.py "glob" out.jpg [cols] [W] [H]"""
import sys, glob, os
from PIL import Image, ImageDraw
fs = sorted(glob.glob(sys.argv[1])); cols = int(sys.argv[3]) if len(sys.argv) > 3 else 16
W = int(sys.argv[4]) if len(sys.argv) > 4 else 200; H = int(sys.argv[5]) if len(sys.argv) > 5 else 300
rows = (len(fs) + cols - 1) // cols
S = Image.new('RGB', (cols * W, rows * H), (20, 40, 90)); d = ImageDraw.Draw(S)
for i, f in enumerate(fs):
    im = Image.open(f).convert('RGBA'); im.thumbnail((W - 6, H - 20)); x, y = (i % cols) * W, (i // cols) * H
    S.paste(im, (x + (W - im.width) // 2, y + 18), im); d.text((x + 3, y + 2), os.path.basename(f)[:-4][-16:], fill=(255, 255, 0))
S.save(sys.argv[2], quality=85); print(S.size)
