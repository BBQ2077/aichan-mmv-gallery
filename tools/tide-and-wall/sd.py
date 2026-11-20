"""本機 sd-server 無頭控制＋批量生圖（沿用 D:/GGUFRun/image-ui.py 的啟動指令與 ROCm 環境）。

用法：
  sd.py start moss8|qwen|qwenedit     啟動（先確認埠空著）
  sd.py stop                          停止（只殺自己記錄的 sd-server.exe PID）
  sd.py status
  sd.py gen jobs.json                 批量；jobs 為 list，每筆：
      {"out": "相對專案路徑.png", "prompt": "...", "w": 2560, "h": 1440, "seed": 1,
       "refs": ["參考圖路徑", ...]   # 只有 qwenedit 用
      }
  已存在的 out 會跳過（可中斷續跑）。
"""
import base64, importlib.util, json, os, pathlib, subprocess, sys, time, urllib.request

GG = pathlib.Path('D:/GGUFRun')
PROJ = pathlib.Path(__file__).resolve().parent.parent
PORT = 18436
URL = f'http://127.0.0.1:{PORT}'
PIDF = PROJ / '_logs' / 'sdserver.pid'
MODEF = PROJ / '_logs' / 'sdserver.mode'
LOG = PROJ / '_logs' / 'sdserver.log'

QWEN_SIGMAS = [1.0, 0.978453, 0.95418, 0.926626, 0.89508, 0.845148, 0.704534, 0.414568, 0]
MOSS = {'moss8': ('moss_image_sft_8step_int8_convrot.safetensors', 8, 'IMAGE-MODELS/moss-image/8step-dmd/dataspace.safetensors',
                  'MOSS-Image-SFT-8-steps-dmd-lora.safetensors'),
        'moss4': ('moss_image_sft_4step_int8_convrot.safetensors', 4, 'IMAGE-MODELS/moss-image/4step/dataspace.safetensors',
                  'MOSS-Image-SFT-4-steps-lora.safetensors')}


def ui():
    spec = importlib.util.spec_from_file_location('imageui', GG / 'image-ui.py')
    m = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(GG))
    spec.loader.exec_module(m)
    return m


def settings_for(mode):
    s = json.loads((GG / 'image-settings.json').read_text(encoding='utf-8'))
    s['cache_mode'] = 'off'
    if mode in MOSS:
        s['runtime'] = 'sd-master-b13a482-moss4-gfx1201-rocm-10.1.0-x64/'
        s['models'] = {'model': '', 'diffusion': 'IMAGE-MODELS/moss-image/' + MOSS[mode][0],
                       'llm': 'IMAGE-MODELS/moss-image/Qwen3.5-9B-Q4_K_M.gguf', 'llm_vision': '', 'clip_l': '',
                       'clip_g': '', 't5xxl': '', 'vae': 'IMAGE-MODELS/moss-image/flux2-vae_small.safetensors'}
        s['extra_args'] = '--tokenizer IMAGE-MODELS/moss-image/tokenizer_qwen3.5.json'
        s['ref_image_args'] = ''
    else:
        s['runtime'] = 'sd-master-f0aac52-bin-win-rocm-10.1.0-x64/'
        s['models'] = {'model': '', 'diffusion': 'IMAGE-MODELS/qwen-image/qwen-image-2.1-turbo-Q4_K_M.gguf',
                       'llm': 'IMAGE-MODELS/qwen-image/Qwen3VL-8B-Instruct-Q4_K_M.gguf',
                       'llm_vision': 'IMAGE-MODELS/qwen-image/mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf',
                       'clip_l': '', 'clip_g': '', 't5xxl': '',
                       'vae': 'IMAGE-MODELS/qwen-image/qwen_image_2.1_vae_bf16.safetensors'}
        s['extra_args'] = ''
        s['ref_image_args'] = 'preset=qwen,vae_input_max_pixels=800000'
    return s


def alive():
    try:
        with urllib.request.urlopen(URL + '/sdapi/v1/loras', timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def start(mode):
    m = ui()
    if m.port_busy(PORT):
        sys.exit(f'埠 {PORT} 已被占用（可能 Image 控制窗在跑）；先關掉再啟動')
    cmd = m.build_cmd_from_settings(GG, PORT, settings_for(mode), vision=(mode == 'qwenedit'), offload=os.environ.get('SD_OFFLOAD', '1') == '1')
    env = m.local_rocm_environment(cmd[0])
    LOG.parent.mkdir(exist_ok=True)
    f = open(LOG, 'w', encoding='utf-8', errors='replace')
    p = subprocess.Popen(cmd, cwd=GG, env=env, stdout=f, stderr=subprocess.STDOUT,
                         creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | 0x08000000)
    PIDF.write_text(str(p.pid)); MODEF.write_text(mode)
    t0 = time.time()
    while time.time() - t0 < 600:
        if p.poll() is not None:
            sys.exit(f'sd-server 結束 exit={p.returncode}，看 {LOG}')
        if alive():
            print(f'ready {mode} pid={p.pid} {time.time()-t0:.0f}s'); return
        time.sleep(2)
    sys.exit('啟動逾時')


def stop():
    if PIDF.exists():
        pid = PIDF.read_text().strip()
        subprocess.run(['taskkill', '/F', '/T', '/PID', pid], capture_output=True)
        PIDF.unlink(); print('stopped', pid)
    r = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq sd-server.exe'], capture_output=True, text=True)
    print('殘留：', 'sd-server.exe' in r.stdout)


def data_url(path):
    return 'data:image/png;base64,' + base64.b64encode(pathlib.Path(path).read_bytes()).decode()


def post(path, body):
    req = urllib.request.Request(URL + path, json.dumps(body).encode(), {'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status, json.loads(r.read())


def gen_one(mode, job):
    w, h = job.get('w', 1024), job.get('h', 1024)
    sp = {'guidance': {'txt_cfg': 1}, 'sample_method': 'euler'}
    native = {'prompt': job['prompt'], 'negative_prompt': '', 'width': w, 'height': h,
              'seed': job.get('seed', 1), 'batch_count': 1, 'init_image': None, 'output_format': 'png'}
    if mode in MOSS:
        _, steps, ds, lora = MOSS[mode]
        sp.update(sample_steps=steps, extra_sample_args='dataspace=' + ds)
        native['lora'] = [{'path': lora, 'multiplier': 1}]
    else:
        sp.update(sample_steps=len(QWEN_SIGMAS) - 1, custom_sigmas=QWEN_SIGMAS)
        if job.get('refs'):
            native['ref_images'] = [data_url(PROJ / r) for r in job['refs']]
    if job.get('init'):
        # 小圖定構圖 → 放大到目標尺寸 → img2img 重繪細節（構圖不變）
        from PIL import Image
        import io
        im = Image.open(PROJ / job['init']).convert('RGB').resize((w, h), Image.LANCZOS)
        buf = io.BytesIO(); im.save(buf, 'PNG')
        native['init_image'] = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()
        native['strength'] = job.get('strength', 0.45)
    native['sample_params'] = sp
    st, sub = post('/sdcpp/v1/img_gen', native)
    if st != 202: raise RuntimeError(f'submit {st} {sub}')
    for _ in range(3600):
        with urllib.request.urlopen(URL + sub['poll_url'], timeout=30) as r:
            j = json.loads(r.read())
        if j['status'] in ('completed', 'succeeded', 'done', 'finished'):
            return base64.b64decode(j['result']['images'][0]['b64_json'])
        if j['status'] in ('failed', 'cancelled', 'canceled'):
            raise RuntimeError(j.get('error') or j['status'])
        time.sleep(0.5)
    raise RuntimeError('timeout')


def gen(jobfile):
    mode = MODEF.read_text().strip()
    jobs = json.loads(pathlib.Path(jobfile).read_text(encoding='utf-8'))
    for k, job in enumerate(jobs, 1):
        out = PROJ / job['out']
        if out.exists() and out.stat().st_size > 0:
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        try:
            png = gen_one(mode, job)
        except Exception as e:
            print(f'[{k}/{len(jobs)}] FAIL {job["out"]}: {e}', flush=True); continue
        out.write_bytes(png)
        print(f'[{k}/{len(jobs)}] {job["out"]} {time.time()-t0:.1f}s', flush=True)


if __name__ == '__main__':
    a = sys.argv[1:]
    {'start': lambda: start(a[1]), 'stop': stop, 'status': lambda: print(alive(), MODEF.read_text() if MODEF.exists() else ''),
     'gen': lambda: gen(a[1])}[a[0]]()
