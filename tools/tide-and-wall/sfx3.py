"""音效層 v3：讀 60_cut/edl2.py 的 SFX 提示點與鏡頭事件，全部用 CC0 錄音取樣。
- 聲床：每場戲一條連續錄音（雨、火、海、風、戰場人聲），場與場之間交叉淡化，不逐鏡斷開。
- 點音：名稱對應取樣；打擊事件（hit/heavy/boom/black）自動配低頻衝擊與金屬聲。
輸出 60_cut/sfx3.wav（48k 立體聲）。"""
import importlib.util, wave, subprocess, glob, os, math
import numpy as np

ROOT = "C:/Users/user/hermes-files/ai-war-mmv"
SR = 48000
rng = np.random.default_rng(23)
DIRS = [ROOT + "/20_audio/sfx_src", ROOT + "/20_audio/sfx_src2", ROOT + "/20_audio/amb_src"]
_FILES = [f for d in DIRS for f in glob.glob(d + "/**/*", recursive=True)
          if f.lower().endswith((".ogg", ".wav", ".mp3", ".flac")) and not os.path.basename(f).startswith("._")]
_C = {}

def find(name):
    hits = [f for f in _FILES if os.path.basename(f) == name] or [f for f in _FILES if name in f.replace("\\", "/")]
    if not hits: raise FileNotFoundError(name)
    return hits[0]

def load(name, ss=0.0, t=None, speed=1.0):
    key = (name, ss, t, speed)
    if key not in _C:
        cmd = ["ffmpeg", "-v", "quiet", "-ss", str(ss)] + (["-t", str(t)] if t else []) + ["-i", find(name), "-ac", "1"]
        cmd += ["-ar", str(int(SR / speed)), "-f", "f32le", "-"]  # 以較低取樣率讀出、照 SR 播放 = 降調放慢
        x = np.frombuffer(subprocess.run(cmd, capture_output=True).stdout, np.float32).astype(np.float64)
        x = x - x.mean() if len(x) else np.zeros(10)
        _C[key] = x / (np.abs(x).max() + 1e-9)
    return _C[key]

def fade(x, a=0.01, b=0.05):
    x = x.copy(); ka, kb = min(len(x) // 2, int(SR * a)), min(len(x) // 2, int(SR * b))
    if ka: x[:ka] *= np.linspace(0, 1, ka)
    if kb: x[-kb:] *= np.linspace(1, 0, kb)
    return x

def env(n, a, d):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / d)

def thump(f0=55, d=0.5, n=None):  # 低頻衝擊（sub）
    n = n or int(SR * d * 4); t = np.arange(n) / SR
    f = f0 + 90 * np.exp(-t * 22)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.002, d)

def whoosh(dur=0.4, rev=False):
    n = int(SR * dur); x = rng.standard_normal(n)
    k = np.linspace(48, 6, n).astype(int); out = np.empty(n); cs = np.concatenate([[0], np.cumsum(x)])
    idx = np.arange(n); lo = np.maximum(0, idx - k)
    out = (cs[idx + 1] - cs[lo]) / (idx + 1 - lo)
    sh = np.sin(np.pi * np.linspace(0, 1, n)) ** 2
    y = out * sh; y /= np.abs(y).max() + 1e-9
    return y[::-1].copy() if rev else y

def loop_to(x, n, xf=0.5):
    """把取樣循環到 n 長度，接縫交叉淡化。"""
    k = int(SR * xf)
    if len(x) >= n: return x[:n].copy()
    out = np.zeros(n); pos = 0; first = True
    while pos < n:
        seg = x.copy()
        if not first: seg[:k] *= np.linspace(0, 1, k)
        seg[-k:] *= np.linspace(1, 0, k)
        L = min(len(seg), n - pos); out[pos:pos + L] += seg[:L]
        pos += len(seg) - k; first = False
    return out

TOTAL = 0; L = R = None
def add(sig, t, g=1.0, pan=0.0):
    i = int(t * SR)
    if i >= TOTAL: return
    if i < 0: sig = sig[-i:]; i = 0
    sig = sig[: TOTAL - i] * g
    L[i:i + len(sig)] += sig * (1 - max(0, pan)); R[i:i + len(sig)] += sig * (1 + min(0, pan))

def pick(names): return names[rng.integers(len(names))]
SWC = [f"sword_clash.{i}.ogg" for i in range(1, 11)]
SWS = [f"sword.{i}.ogg" for i in range(1, 11)]
IMH = [f"impactMetal_heavy_00{i}.ogg" for i in range(5)]
IPH = [f"impactPlate_heavy_00{i}.ogg" for i in range(5)]
IPU = [f"impactPunch_heavy_00{i}.ogg" for i in range(5)]
IWH = [f"impactWood_heavy_00{i}.ogg" for i in range(5)]
CLM = [f"clamour{i}.wav" for i in range(1, 12)]

def dragon_roar(d=2.2):
    a = load(pick(["monster_04.ogg", "monster_07.ogg", "creature_roar_03.ogg", "creature_roar_02.ogg"]), speed=0.55)
    b = load("giant1.wav", speed=0.6)
    n = int(SR * d); out = np.zeros(n)
    for s, g, o in ((a, 1.0, 0), (b, 0.6, 0.05), (a, 0.5, 0.12)):
        L_ = min(len(s), n - int(o * SR)); out[int(o * SR):int(o * SR) + L_] += s[:L_] * g
    nz = np.convolve(rng.standard_normal(n), np.ones(80) / 80, "same") * 6 * env(n, 0.05, d * 0.5)
    return fade(out + nz, 0.02, 0.4)

def gallop(d=2.5, horses=3):
    n = int(SR * d); out = np.zeros(n)
    for h in range(horses):
        s = load(pick(["grass.mp3", "ground.mp3"])); per = rng.uniform(0.40, 0.47); t = rng.uniform(0, 0.3)
        while t < d:
            i = int(t * SR); L_ = min(len(s), n - i); out[i:i + L_] += s[:L_] * rng.uniform(0.5, 1.0); t += per
    return fade(out / max(1, horses * 0.6), 0.05, 0.4)

def march(d=2.5):
    n = int(SR * d); out = np.zeros(n); t = 0.0
    steps = [f"hard-footstep{i}.wav" for i in range(1, 5)]
    while t < d:
        for k in range(4):
            s = load(pick(steps)); i = int((t + rng.uniform(0, 0.04)) * SR); L_ = min(len(s), n - i)
            if L_ > 0: out[i:i + L_] += s[:L_] * rng.uniform(0.3, 0.6)
        t += 0.43
    ch = load(pick(["chainmail1.wav", "chainmail2.wav"])); out[:min(n, len(ch))] += ch[:n] * 0.5
    return fade(out, 0.05, 0.3)

def horn():
    return fade(load("war_horns.wav", ss=0.0, t=6.0), 0.02, 1.2)

def arrows(d=1.6):
    n = int(SR * d); out = np.zeros(n)
    for _ in range(14):
        s = load(pick(["swing.wav", "swing2.wav", "swing3.wav"]), speed=rng.uniform(1.2, 1.7))
        i = int(rng.uniform(0, d * 0.7) * SR); L_ = min(len(s), n - i); out[i:i + L_] += s[:L_] * rng.uniform(0.2, 0.5)
    return out

def S_(name):
    """名稱 → [(訊號, 增益, 延遲, 聲像)]"""
    p = lambda: rng.uniform(-0.35, 0.35)
    if name == "clash": return [(load(pick(SWC)), 0.9, 0, p()), (load(pick(IMH)), 0.5, 0.01, 0), (thump(60, 0.25), 0.5, 0, 0)]
    if name == "blade": return [(load(pick(["sword-unsheathe.wav", "sword-unsheathe2.wav", "sword-unsheathe3.wav"])), 0.8, 0, 0)]
    if name == "whoosh": return [(whoosh(0.45), 0.45, 0, p())]
    if name == "anvil": return [(load(pick([f"impactBell_heavy_00{i}.ogg" for i in range(5)])), 0.8, 0, 0), (load("metal-ringing.wav"), 0.35, 0, 0)]
    if name == "hooves": return [(gallop(2.6), 0.55, 0, 0)]
    if name == "charge": return [(gallop(3.0, 5), 0.6, 0, 0), (load("crowd_shouting_0.ogg", ss=3, t=3), 0.45, 0.1, 0)]
    if name == "march": return [(march(2.6), 0.6, 0, 0)]
    if name == "coins": return [(load(pick(["handleCoins.ogg", "item_coins_02.ogg", "item_coins_03.ogg"])), 0.8, 0.03, 0), (load("coin2.wav"), 0.4, 0.3, 0.2)]
    if name == "drum": return [(thump(48, 0.55), 0.8, 0, 0), (thump(48, 0.45), 0.6, 0.43, 0)]
    if name == "roar": return [(dragon_roar(2.2), 0.75, 0, 0)]
    if name == "fire_in": return [(fade(load(pick(["spell_fire_03.ogg", "spell_fire_04.ogg"])), 0.01, 0.3), 0.6, 0, 0)]
    if name == "dragonfire": return [(dragon_roar(2.5), 0.7, 0, 0), (fade(load("spell_fire_03.ogg", speed=0.6), 0.01, 0.6), 0.9, 0.15, 0), (thump(40, 0.9), 0.7, 0.1, 0)]
    if name == "shout": return [(fade(load("crowd_shouting_0.ogg", ss=rng.uniform(2, 20), t=1.8), 0.05, 0.6), 0.7, 0, 0)]
    if name == "cheer": return [(fade(load("crowd_shouting_0.ogg", ss=8, t=3.5), 0.2, 1.0), 0.75, 0, 0)]
    if name == "ballista": return [(load(pick(IWH)), 0.7, 0, 0), (whoosh(0.35), 0.5, 0.03, 0.2), (load("creak1.ogg"), 0.4, 0, 0)]
    if name == "horn": return [(horn(), 0.65, 0, 0)]
    if name == "stab": return [(load(pick(["knifeSlice.ogg", "knifeSlice2.ogg"])), 0.8, 0, 0), (load(pick(IPU)), 0.7, 0.02, 0), (thump(50, 0.3), 0.6, 0, 0)]
    if name == "wood_break": return [(load(pick([f"bfh1_wood_breaking_0{i}.ogg" for i in range(1, 5)])), 0.9, 0, 0), (thump(45, 0.5), 0.7, 0, 0)]
    if name == "collapse": return [(load(pick([f"bfh1_rock_falling_0{i}.ogg" for i in range(1, 10)])), 0.8, 0.05, 0), (load("explosion.ogg"), 0.8, 0, 0),
                                   (load("far_expl.mp3"), 0.5, 0.15, 0), (load("earthquake.wav", t=3.0), 0.5, 0, 0)]
    if name == "rubble": return [(load(pick([f"bfh1_rock_breaking_0{i}.ogg" for i in range(1, 4)])), 0.9, 0, 0), (load("explosion.ogg"), 0.6, 0, 0)]
    if name == "chain": return [(load(pick(["chain_01.ogg", "chain_03.ogg"])), 0.8, 0, 0), (load("metalLatch.ogg"), 0.7, 0.25, 0)]
    if name == "gong": return [(load("gong_01.ogg"), 0.7, 0, 0), (thump(38, 1.2), 0.8, 0, 0)]
    if name == "wave": return [(fade(load("wave_01_cc0", ), 0.1, 0.8), 0.6, 0, 0)]
    if name == "water": return [(load("splash_01.ogg"), 0.6, 0, 0), (fade(load("wave_02_cc0"), 0.1, 0.8), 0.5, 0.1, 0)]
    if name == "page": return [(load(pick(["bookFlip1.ogg", "bookFlip2.ogg", "pageturn1.wav"])), 0.6, 0.05, 0)]
    if name == "bell": return [(load(pick(["bell_01.ogg", "bell_02.ogg"])), 0.5, 0, 0)]
    if name == "arrows": return [(arrows(1.8), 0.7, 0, 0)]
    if name == "arrow": return [(load("swing2.wav", speed=1.4), 0.6, 0, 0.2), (load(pick(IWH)), 0.4, 0.25, 0)]
    if name == "creak": return [(load(pick(["creak1.ogg", "creak2.ogg", "creak3.ogg"])), 0.6, 0, 0)]
    if name == "bowdraw": return [(load("creak2.ogg", speed=1.3), 0.5, 0, 0)]
    if name == "chop": return [(load("chop.ogg"), 0.9, 0, 0), (load(pick(IPU)), 0.7, 0, 0), (thump(42, 0.6), 0.9, 0, 0)]
    if name == "thunder": return [(fade(load("sfx100v2_thunder_01.ogg"), 0.01, 1.0), 0.9, 0, 0), (thump(35, 1.0), 0.5, 0, 0)]
    if name == "wind": return [(fade(load("wind2.wav", ss=5, t=4), 0.6, 1.5), 0.5, 0, 0)]
    if name == "door": return [(load(pick(["doorClose_1.ogg", "doorClose_3.ogg"])), 0.9, 0, 0), (thump(45, 0.5), 0.7, 0, 0)]
    if name == "door_open": return [(load(pick(["doorOpen_1.ogg", "door_open.ogg"])), 0.7, 0, 0)]
    if name == "steam": return [(fade(load("sfx100v2_air_01.ogg"), 0.02, 0.5), 0.6, 0, 0), (load("metal_05.ogg"), 0.3, 0, 0)]
    if name == "land": return [(load(pick(IPH)), 0.8, 0, 0), (thump(45, 0.5), 0.9, 0, 0)]
    if name == "slam": return [(load(pick(IWH)), 1.0, 0, 0), (thump(50, 0.4), 0.9, 0, 0)]
    if name == "metal_click": return [(load("metalClick.ogg"), 0.7, 0, 0)]
    if name == "piece": return [(load("impactWood_medium_002.ogg"), 0.8, 0, 0), (thump(60, 0.3), 0.4, 0, 0)]
    if name == "wagon": return [(fade(load("rolling.ogg"), 0.3, 0.6), 0.4, 0, 0), (load("creak3.ogg"), 0.4, 0.3, 0)]
    if name == "shield_wall": return [(load(IPH[0]), 0.8, 0, -0.3), (load(IPH[2]), 0.8, 0.05, 0.3), (load(pick(IWH)), 0.7, 0.03, 0), (thump(50, 0.5), 0.9, 0, 0)]
    if name == "ricochet": return [(load("impactMetal_light_002.ogg"), 0.7, 0, 0), (load(pick(SWS)), 0.5, 0.02, 0.3)]
    if name == "gate": return [(load("doorOpen_2.ogg", speed=0.7), 0.8, 0, 0), (load("chain_03.ogg"), 0.6, 0.1, 0)]
    if name == "portcullis": return [(load("chain_03.ogg", speed=0.8), 0.7, 0, 0), (load("bfh1_metal_falling_02.ogg"), 0.8, 0.3, 0), (load(IMH[1]), 0.9, 0.7, 0), (thump(40, 0.7), 0.9, 0.7, 0)]
    if name == "blade_drop": return [(load("bfh1_metal_falling_01.ogg"), 0.8, 0.1, 0.2)]
    if name == "key": return [(load("key_open_01.ogg"), 0.8, 0, 0)]
    print("未對應音效:", name); return []

# 聲床：(起, 迄, 取樣函式, 增益, 淡入淡出秒)
def bed_src(kind, n):
    if kind == "rain": return load("amb_rain2.ogg", ss=60, t=n / SR + 1)[:n]
    if kind == "fire": return loop_to(load("fire_place.wav"), n, 1.0)
    if kind == "sea": return load("Vistula.mp3", ss=1200, t=n / SR + 1)[:n]
    if kind == "wind": return loop_to(load("wind1.wav"), n, 2.0)
    if kind == "battle":
        x = loop_to(load("crowd_shouting_0.ogg"), n, 1.5)
        for t in np.arange(0, n / SR, 0.35):  # 遠處兵器碰撞、喧嘩
            s = load(pick(CLM + SWC)); i = int((t + rng.uniform(0, 0.3)) * SR); L_ = min(len(s), n - i)
            if L_ > 0: x[i:i + L_] += s[:L_] * rng.uniform(0.05, 0.22)
        return x
    raise ValueError(kind)

BEDS = [
    (0.0, 13.8, "fire", 0.25, 1.0), (0.0, 16.0, "wind", 0.25, 1.5),
    (42.2, 52.0, "fire", 0.18, 1.5), (49.5, 60.5, "sea", 0.35, 2.0),
    (76.2, 96.0, "wind", 0.15, 2.0),
    (96.0, 150.5, "sea", 0.35, 2.0), (112.6, 150.5, "battle", 0.30, 1.0), (112.6, 150.5, "fire", 0.28, 2.0),
    (150.5, 180.5, "wind", 0.12, 2.0), (169.0, 180.0, "battle", 0.15, 1.5),
    (182.0, 207.0, "rain", 0.55, 2.5), (182.0, 207.0, "wind", 0.18, 2.5),
    (206.3, 250.0, "battle", 0.32, 0.8), (222.0, 250.0, "fire", 0.40, 1.0),
    (248.0, 264.5, "wind", 0.35, 2.5),
    (264.3, 289.5, "battle", 0.30, 1.0), (267.0, 289.5, "fire", 0.20, 2.0),
    (289.2, 306.5, "fire", 0.50, 0.8),
    (306.2, 319.0, "wind", 0.15, 2.0),
]

def main():
    global TOTAL, L, R
    sp = importlib.util.spec_from_file_location("edl2", f"{ROOT}/60_cut/edl2.py")
    m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
    end = m.SHOTS[-1]["t1"]; TOTAL = int(SR * (end + 2)); L = np.zeros(TOTAL); R = np.zeros(TOTAL)
    # 聲床
    for a, b, kind, g, f in BEDS:
        n = int((b - a) * SR); x = bed_src(kind, n)
        x = x / (np.sqrt(np.mean(x ** 2)) + 1e-9) * 0.12  # 以 RMS 對齊
        add(fade(x, f, f), a, g, 0)
    # 點音
    for t, name, *rest in m.SFX:
        for sig, g, dl, pan in S_(name): add(sig, t + dl, g * (rest[0] if rest else 1.0), pan)
    # 鏡頭事件
    for s in m.SHOTS:
        has_ch = bool(s.get("ch")) or "split" in s
        for ev in s.get("ev", []):
            t = s["t0"] + ev[0]; k = ev[1]
            if k == "tap":
                add(load(pick(SWC if has_ch else IPU)), t, 0.3, rng.uniform(-0.3, 0.3))
            elif k == "hit":
                add(thump(55, 0.35), t, 0.55)
                add(load(pick(SWC if has_ch else IPU)), t, 0.5, rng.uniform(-0.3, 0.3))
                add(whoosh(0.22, True), t - 0.2, 0.18)
            elif k == "heavy":
                add(thump(42, 0.7), t, 0.9); add(load(pick(IPH)), t, 0.5)
                add(load(pick(SWC)) if has_ch else load(pick(IWH)), t, 0.5)
                add(whoosh(0.35, True), t - 0.33, 0.3)
            elif k == "boom":
                add(load("explosion.ogg"), t, 0.9); add(load("far_expl.mp3"), t + 0.08, 0.5); add(thump(36, 1.0), t, 0.9)
            elif k == "flash":
                add(whoosh(0.3, True), t - 0.28, 0.25); add(thump(70, 0.2), t, 0.3)
            elif k == "black":
                add(thump(38, 0.8), t, 0.7)
            elif k == "white_out":
                add(whoosh(ev[2] + 0.2, True), t, 0.3)
    # 匯流排：軟限幅
    mx = np.percentile(np.abs(np.concatenate([L, R])), 99.97) + 1e-9
    L2, R2 = np.tanh(L / mx * 1.2) / np.tanh(1.2), np.tanh(R / mx * 1.2) / np.tanh(1.2)
    st = (np.stack([L2, R2], 1) * 0.9 * 32767).clip(-32767, 32767).astype(np.int16)
    with wave.open(f"{ROOT}/60_cut/sfx3.wav", "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(st.tobytes())
    print("sfx3.wav", len(st) / SR)

if __name__ == "__main__":
    main()
