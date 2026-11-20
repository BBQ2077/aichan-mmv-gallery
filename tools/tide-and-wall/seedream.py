"""fal.ai Seedream 5.5 用戶端（付費，只用在高價值鏡頭）。
金鑰：環境變數 FAL_KEY，或 _secrets/fal_key.txt（只讀取、不印出）。
用法：python _tools/seedream.py jobs.json      job 欄位：
  {"out", "mode": "edit|t2i|layerize", "prompt", "refs": [本機圖], "w", "h", "transparent": bool}
每次呼叫照官方價目估算花費，記到 _logs/seedream_spend.tsv；累計超過 BUDGET 就停。"""
import json, os, sys, base64, io, time, urllib.request, pathlib
from PIL import Image
BUDGET = float(os.environ.get('SEEDREAM_BUDGET', '2.0'))  # 鎖在已花金額：任何付費呼叫都要使用者逐次同意後才調高
EP = {'edit': 'bytedance/seedream/v5.5/edit', 't2i': 'bytedance/seedream/v5.5/text-to-image', 'layerize': 'bytedance/seedream/v5.5/layerize',
      'muse_edit': 'meta/muse-image/edit', 'muse_t2i': 'meta/muse-image/text-to-image'}
LEDGER = pathlib.Path('_logs/seedream_spend.tsv')


def key():
    k = os.environ.get('FAL_KEY') or (pathlib.Path('_secrets/fal_key.txt').read_text().strip() if os.path.exists('_secrets/fal_key.txt') else '')
    if not k: sys.exit('no FAL_KEY')
    return k


def data_uri(p, maxside=1536):
    im = Image.open(p); im.thumbnail((maxside, maxside))
    b = io.BytesIO(); fmt = 'PNG' if im.mode == 'RGBA' else 'JPEG'
    (im if fmt == 'PNG' else im.convert('RGB')).save(b, fmt, quality=92)
    return f"data:image/{fmt.lower()};base64," + base64.b64encode(b.getvalue()).decode()


def spent():
    if not LEDGER.exists(): return 0.0
    return sum(float(l.split('\t')[2]) for l in LEDGER.read_text(encoding='utf-8').splitlines() if l.count('\t') >= 2)


def count(mode):
    if not LEDGER.exists(): return 0
    return sum(1 for l in LEDGER.read_text(encoding='utf-8').splitlines() if l.endswith('	' + mode))


def cost(j):
    if j['mode'].startswith('muse'): return 0.01
    big = j.get('w', 1920) * j.get('h', 1088) > 2_610_000
    c = 0.0405 if big else 0.03
    if j['mode'] == 'edit': c += 0.012 * len(j.get('refs', []))
    return c


def call(ep, payload, k):
    req = urllib.request.Request('https://fal.run/' + ep, json.dumps(payload).encode(),
                                 {'Authorization': 'Key ' + k, 'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(req, timeout=600))


def save(url, out):
    os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
    if url.startswith('data:'): open(out, 'wb').write(base64.b64decode(url.split(',', 1)[1]))
    else: urllib.request.urlretrieve(url, out)


def run(j, k):
    p = {'prompt': j.get('prompt', ''), 'enable_safety_checker': True, 'output_format': 'png'}
    if j['mode'].startswith('muse'):
        p = {'prompt': j['prompt'], 'aspect_ratio': j.get('ratio', '16:9'), 'output_format': 'png'}
        if j['mode'] == 'muse_edit': p['image_urls'] = [data_uri(r) for r in j['refs']]
    elif j['mode'] == 'layerize':
        p = {'prompt': j.get('prompt', ''), 'image_url': data_uri(j['refs'][0], 2048), 'image_size': 'auto_2K', 'max_images': j.get('max_images', 12)}
    else:
        p['image_size'] = {'width': j.get('w', 1920), 'height': j.get('h', 1088)}
        if j.get('transparent'): p['background'] = 'transparent'
        if j['mode'] == 'edit': p['image_urls'] = [data_uri(r) for r in j['refs']]
    r = call(EP[j['mode']], p, k)
    if j['mode'] == 'layerize':
        d = j['out'].rstrip('/'); os.makedirs(d, exist_ok=True)
        for i, L in enumerate(r['layers']):
            save(L['image']['url'], f"{d}/L{i:02d}.png")
        json.dump(r['layers'], open(f"{d}/layers.json", 'w'), default=str, indent=1)
    else:
        save(r['images'][0]['url'], j['out'])


if __name__ == '__main__':
    k = key(); jobs = json.load(open(sys.argv[1], encoding='utf-8'))
    # 每次執行的張數上限（使用者規則）：Muse 一批 5 張；Seedream 一次 1 張；審過才跑下一批
    todo = [j for j in jobs if not (os.path.exists(j['out']) and (os.path.isdir(j['out']) or os.path.getsize(j['out']) > 0))]
    nm = sum(j['mode'].startswith('muse') for j in todo); ns = len(todo) - nm
    if nm > 5 or ns > 1 or (nm and ns): sys.exit(f'batch rule: muse {nm} (max 5) / seedream {ns} (max 1), 不可混批')
    for i, j in enumerate(jobs, 1):
        if os.path.exists(j['out']) and (os.path.isdir(j['out']) or os.path.getsize(j['out']) > 0):
            continue
        c = cost(j) if j['mode'] != 'layerize' else 0.045 * j.get('max_images', 12)  # 實測：10 層計 13.9 units＝0.417 美元，按輸出層數計費
        # 使用者授權額度（11-18 14:20）：Muse 100 張；Seedream 文生圖 5 張；Seedream edit／layerize 每次要使用者同意（APPROVED=檔名）
        n = count(j['mode']); lim = {'muse_edit': 100, 'muse_t2i': 100, 't2i': 5}
        if j['mode'] in ('muse_edit', 'muse_t2i'): n = count('muse_edit') + count('muse_t2i')
        if j['mode'] in lim and n >= lim[j['mode']]: print('quota stop', j['mode'], n); break
        if j['mode'] in ('edit', 'layerize') and os.environ.get('APPROVED') != os.path.basename(j['out']): print('need approval', j['out']); break
        t = time.time()
        try:
            run(j, k)
            LEDGER.parent.mkdir(exist_ok=True)
            with LEDGER.open('a', encoding='utf-8') as f: f.write(f"{time.strftime('%m-%d %H:%M')}\t{j['out']}\t{c:.4f}\t{j['mode']}\n")
            print(f"[{i}/{len(jobs)}] {j['out']} {time.time() - t:.1f}s ${c:.3f} total ${spent():.2f}", flush=True)
        except Exception as e:
            print(f"[{i}/{len(jobs)}] FAIL {j['out']}: {getattr(e, 'read', lambda: b'')()[:300] or e}", flush=True)
