"""抽格：python stills.py out.jpg [cols] t1 t2 ...  或  python stills.py out.jpg cols mid（每鏡中點）／ start-end:step"""
import sys, os, time, importlib.util
from PIL import Image, ImageDraw
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location('edl', R + '/60_cut/' + os.environ.get('EDL', 'edl.py')); E = importlib.util.module_from_spec(spec); spec.loader.exec_module(E)
import eng
out = sys.argv[1]; cols = int(sys.argv[2]); args = sys.argv[3:]
ts = []
for a in args:
    if a == 'mid':
        t = 0
        for s in E.SHOTS: ts.append(t + s.dur * 0.6); t += s.dur
    elif '-' in a and ':' in a:
        r, st = a.split(':'); a0, a1 = map(float, r.split('-')); x = a0
        while x < a1: ts.append(round(x, 3)); x += float(st)
    else: ts.append(float(a))
tw, th = 480, 270; rows = (len(ts) + cols - 1) // cols
S = Image.new('RGB', (cols * tw, rows * (th + 22)), (30, 30, 30)); d = ImageDraw.Draw(S)
t_ = time.time()
for i, t in enumerate(ts):
    im = eng.frame(E.SHOTS, E.EV, t).resize((tw, th), Image.LANCZOS)
    x, y = (i % cols) * tw, (i // cols) * (th + 22); S.paste(im, (x, y + 22))
    tt = 0; nm = ''
    for s in E.SHOTS:
        if t < tt + s.dur: nm = s.name; break
        tt += s.dur
    d.text((x + 4, y + 3), f'{t:.2f} {nm}', fill=(255, 255, 0))
S.save(out, quality=85); print(out, S.size, f'{(time.time() - t_) / len(ts):.2f}s/frame')
