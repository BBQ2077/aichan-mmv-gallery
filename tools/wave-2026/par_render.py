"""平行渲染：python par_render.py out.mp4 [N] [mix.wav]
整片切 N 段（整格對齊）各開一個程序，最後 concat 再接上混音。"""
import os, sys, subprocess, time, importlib.util
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

if len(sys.argv) > 1 and sys.argv[1] == '--seg':
    _, _, a, b, out = sys.argv
    spec = importlib.util.spec_from_file_location('edl', R + '/60_cut/' + os.environ.get('EDL', 'edl.py')); E = importlib.util.module_from_spec(spec); spec.loader.exec_module(E)
    sys.path.insert(0, T); import eng
    eng.render(E.SHOTS, E.EV, out, float(a), float(b), fast=True)
    sys.exit(0)

out = sys.argv[1]; N = int(sys.argv[2]) if len(sys.argv) > 2 else 12
mix = sys.argv[3] if len(sys.argv) > 3 else None
spec = importlib.util.spec_from_file_location('edl', R + '/60_cut/' + os.environ.get('EDL', 'edl.py')); E = importlib.util.module_from_spec(spec); spec.loader.exec_module(E)
sys.path.insert(0, T); import eng
total = sum(s.dur for s in E.SHOTS); nf = int(round(total * eng.FPS))
tmp = os.path.splitext(out)[0] + '_seg'; os.makedirs(tmp, exist_ok=True)
bounds = [round(nf * k / N) for k in range(N + 1)]
procs = []; t0 = time.time()
for k in range(N):
    seg = f'{tmp}/s{k:02d}.mp4'
    procs.append(subprocess.Popen([PY, os.path.abspath(__file__), '--seg', str(bounds[k] / eng.FPS), str(bounds[k + 1] / eng.FPS), seg],
                                  stdout=open(f'{tmp}/s{k:02d}.log', 'w'), stderr=subprocess.STDOUT))
for p in procs: p.wait()
bad = [k for k, p in enumerate(procs) if p.returncode]
if bad: print('失敗段', bad); sys.exit(1)
open(f'{tmp}/list.txt', 'w').write(''.join(f"file 's{k:02d}.mp4'\n" for k in range(N)))
silent = os.path.splitext(out)[0] + '_noSFX.mp4'
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', f'{tmp}/list.txt', '-c', 'copy', silent], check=True)
if mix:
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', silent, '-i', mix, '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '256k',
                    '-shortest', out], check=True)
print(out, f'{nf} frames', f'{time.time() - t0:.0f}s')
