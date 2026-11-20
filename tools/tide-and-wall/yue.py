"""yue2.cpp 伺服器無頭控制（ROCm）。一次只跑一個程序。
用法：
  yue.py start | stop
  yue.py gen request.json outprefix     → outprefix_N.mp3 / outprefix_N.json（每軌一組）
"""
import json, os, pathlib, re, subprocess, sys, time, urllib.request

APP = pathlib.Path('D:/AI APP/yue2-cpp')
REL = APP / 'build' / 'Release-rocm'
PROJ = pathlib.Path(__file__).resolve().parent.parent
PORT = 8087
URL = f'http://127.0.0.1:{PORT}'
PIDF = PROJ / '_logs' / 'yue.pid'
LOG = PROJ / '_logs' / 'yue.log'


def busy():
    r = subprocess.run(['tasklist'], capture_output=True, text=True).stdout
    return [n for n in ('sd-server.exe', 'sd-cli.exe', 'llama-server.exe', 'yue-server.exe') if n in r]


def health():
    try:
        with urllib.request.urlopen(URL + '/health', timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def start():
    b = busy()
    if b: sys.exit(f'GPU 上已有程序：{b}，不啟動')
    env = dict(os.environ)
    env['PATH'] = f'{REL};{REL / "rocmlib" / "bin"};' + env['PATH']
    env['GGML_BACKEND'] = 'ROCm0'
    cmd = [str(REL / 'yue-server.exe'), '--host', '127.0.0.1', '--port', str(PORT), '--max-batch', os.environ.get('YUE_BATCH', '1'), '--keep-loaded',
           '--model', str(APP / 'models' / 'YuE2-3B-Q8_0.gguf'), '--vae', str(APP / 'models' / 'YuE2-Vae-F32.gguf')]
    LOG.parent.mkdir(exist_ok=True)
    p = subprocess.Popen(cmd, cwd=str(APP), env=env, stdout=open(LOG, 'w', encoding='utf-8'), stderr=subprocess.STDOUT,
                         creationflags=0x08000000)
    PIDF.write_text(str(p.pid))
    for i in range(300):
        if health():
            print('ready yue pid', p.pid, f'{i}s'); return
        if p.poll() is not None: sys.exit('server exited, see ' + str(LOG))
        time.sleep(1)
    sys.exit('timeout')


def stop():
    if PIDF.exists():
        subprocess.run(['taskkill', '/F', '/T', '/PID', PIDF.read_text().strip()], capture_output=True)
        PIDF.unlink()
    time.sleep(2)
    subprocess.run(['taskkill', '/F', '/IM', 'yue-server.exe'], capture_output=True)
    print('殘留：', busy())


def gen(reqfile, prefix):
    body = pathlib.Path(reqfile).read_bytes()
    req = urllib.request.Request(URL + '/synth', body, {'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=60) as r:
        j = json.loads(r.read())
    jid = j.get('id', j.get('job_id'))
    t0 = time.time(); last = None
    while True:
        with urllib.request.urlopen(f'{URL}/job?id={jid}', timeout=30) as r:
            st = json.loads(r.read())
        s = st.get('status')
        if s != last: print(f'[{time.time()-t0:.0f}s] {s}', flush=True); last = s
        if s in ('done', 'completed', 'succeeded', 'finished'): break
        if s in ('failed', 'cancelled', 'error'): sys.exit(json.dumps(st))
        time.sleep(2)
    with urllib.request.urlopen(f'{URL}/job?id={jid}&result=1', timeout=120) as r:
        ctype = r.headers['Content-Type']; data = r.read()
    bnd = re.search(r'boundary="?([^";]+)', ctype).group(1).encode()
    parts = [p for p in data.split(b'--' + bnd) if p.strip() not in (b'', b'--')]
    n = 0; out = pathlib.Path(prefix); out.parent.mkdir(parents=True, exist_ok=True)
    for p in parts:
        head, _, payload = p.lstrip(b'\r\n').partition(b'\r\n\r\n')
        payload = payload.rstrip(b'\r\n')
        h = head.decode('latin1').lower()
        if 'json' in h:
            n += 1; pathlib.Path(f'{prefix}_{n}.json').write_bytes(payload)
        elif 'audio' in h:
            ext = 'wav' if 'wav' in h else 'mp3'
            pathlib.Path(f'{prefix}_{n}.{ext}').write_bytes(payload)
    print(f'done {time.time()-t0:.0f}s tracks={n}')


if __name__ == '__main__':
    a = sys.argv[1:]
    {'start': start, 'stop': stop}.get(a[0], lambda: gen(a[1], a[2]))()
