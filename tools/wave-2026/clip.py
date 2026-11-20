"""樣片：python clip.py out.mp4 mix.wav a1 b1 [a2 b2 ...]，每段 4 程序平行，接起來配混音的對應段"""
import os, sys, subprocess
T = os.path.dirname(os.path.abspath(__file__)); PY = sys.executable
NL = chr(10)
out, mix = sys.argv[1], sys.argv[2]; rs = list(map(float, sys.argv[3:]))
tmp = os.path.splitext(out)[0] + '_seg'; os.makedirs(tmp, exist_ok=True)


def lst(path, files):
    with open(path, 'w', encoding='utf-8') as f:
        for v in files:
            f.write("file '" + os.path.basename(v) + "'" + NL)


procs = []; parts = []; k = 0
for a, b in zip(rs[::2], rs[1::2]):
    fa, fb = round(a * 24), round(b * 24); bd = [fa + (fb - fa) * j // 4 for j in range(5)]; vs = []
    for j in range(4):
        seg = f'{tmp}/c{k:02d}.mp4'; k += 1; vs.append(seg)
        procs.append(subprocess.Popen([PY, T + '/par_render.py', '--seg', str(bd[j] / 24), str(bd[j + 1] / 24), seg],
                                      stdout=open(seg + '.log', 'w'), stderr=subprocess.STDOUT))
    parts.append((a, b, vs))
for p in procs:
    p.wait()
bad = [i for i, p in enumerate(procs) if p.returncode]
if bad:
    print('fail', bad); sys.exit(1)
outs = []
for i, (a, b, vs) in enumerate(parts):
    lst(f'{tmp}/l{i}.txt', vs)
    sv = f'{tmp}/v{i}.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', f'{tmp}/l{i}.txt', '-c', 'copy', sv], check=True)
    po = f'{tmp}/p{i}.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', sv, '-ss', str(a), '-t', str(b - a), '-i', mix, '-map', '0:v', '-map', '1:a',
                    '-c:v', 'libx264', '-crf', '18', '-preset', 'fast', '-c:a', 'aac', '-b:a', '256k', '-shortest', po], check=True)
    outs.append(po)
lst(f'{tmp}/all.txt', outs)
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', f'{tmp}/all.txt', '-c', 'copy', out], check=True)
print(out)
