"""RealESRGAN anime x4 放大（本機 sd-cli，GPU 一次一張）。
用法: python upscale.py help | python upscale.py in.png out.png"""
import sys, subprocess, importlib.util
GG = "D:/GGUFRun"
EXE = GG + "/RUNTIMES/sd-master-f0aac52-bin-win-rocm-10.1.0-x64/sd-cli.exe"
sys.path.insert(0, GG)
spec = importlib.util.spec_from_file_location("ui", GG + "/image-ui.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
env = m.local_rocm_environment(EXE)
if sys.argv[1] == "help":
    r = subprocess.run([EXE, "--help"], cwd=GG, env=env, capture_output=True, text=True, errors="replace")
    print(r.stdout[-6000:], r.stderr[-2000:])
else:
    cmd = [EXE, "-M", "upscale", "--upscale-model", GG + "/IMAGE-MODELS/upscalers/RealESRGAN_x4plus_anime_6B.pth",
           "-i", sys.argv[1], "-o", sys.argv[2]]
    r = subprocess.run(cmd, cwd=GG, env=env, capture_output=True, text=True, errors="replace")
    print(r.returncode, r.stdout[-400:], r.stderr[-400:])
