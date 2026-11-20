"""列出指定時間點所在的鏡：python shotinfo.py t1,t2,...  （EDL2 環境變數可指定剪輯表）"""
import sys, os, importlib.util
ROOT = "C:/Users/user/hermes-files/ai-war-mmv"
sp = importlib.util.spec_from_file_location("edl2", os.environ.get("EDL2", f"{ROOT}/60_cut/edl2.py"))
m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
S = m.SHOTS
def brief(s):
    if "split" in s: return "SPLIT[" + brief(s["split"]["a"]) + " | " + brief(s["split"]["b"]) + "]"
    bg = s.get("bg", ("col",))
    b = bg[0] + (":" + os.path.basename(str(bg[1])) if bg[0] in ("img",) else ":" + str(bg[1:3]) if bg[0] == "card" else "")
    ch = [c.get("p") or ("rig:" + c.get("rig", "")) for c in s.get("ch", [])]
    return f"{b} ch={ch} fac={s.get('fac')} tex={os.path.basename(s['tex'][0]) if s.get('tex') else ''}"
for t in [float(x) for x in sys.argv[1].split(",")]:
    for i, s in enumerate(S):
        if s["t0"] <= t < s["t1"]:
            print(f"{t:7.2f} #{i} [{s['t0']:.2f}-{s['t1']:.2f}] {brief(s)} ev={[e[1] for e in s.get('ev', [])]} txt={[x.get('big') for x in s.get('txt', [])]}")
            break
