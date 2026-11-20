#!/bin/bash
# 平行渲染 v2：edl2 + render2，切 N 段（整秒邊界），最後 concat。
# 用法: bash _tools/par_render2.sh <out.mp4> [N=10] [EDL=60_cut/edl2.py]
cd /c/Users/user/hermes-files/ai-war-mmv
PY="C:/Users/user/hermes-files/WOOF/.venv/Scripts/python.exe"
OUT=$1; N=${2:-10}; export EDL2=${3:-60_cut/edl2.py}
END=$("$PY" -c "
import importlib.util
s=importlib.util.spec_from_file_location('e','$EDL2');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
print(m.SHOTS[-1]['t1'])")
SEG=$("$PY" -c "import math;print(math.ceil($END/$N))")
mkdir -p 60_cut/seg2 _logs; rm -f 60_cut/seg2/*.mp4 60_cut/seg2/list.txt
pids=""
for i in $(seq 0 $((N-1))); do
  a=$((i*SEG)); b=$(( (i+1)*SEG ))
  if [ $i -eq $((N-1)) ]; then b=$END; fi
  "$PY" -u _tools/render2.py --out 60_cut/seg2/s$i.mp4 $a $b > _logs/r2seg$i.log 2>&1 &
  pids="$pids $!"
  echo "file 's$i.mp4'" >> 60_cut/seg2/list.txt
done
wait $pids
ffmpeg -y -loglevel error -f concat -safe 0 -i 60_cut/seg2/list.txt -c copy "$OUT"
echo "done $OUT"
