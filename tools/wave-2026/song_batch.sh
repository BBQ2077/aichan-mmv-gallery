#!/bin/bash
# 用法：bash _tools/song_batch.sh rock:11,edm:21,...   依序生成（GPU 一次一個），完成後停伺服器
cd "$(dirname "$0")/.." || exit 1
P="C:/Users/user/hermes-files/WOOF/.venv/Scripts/python.exe"
n=$(tasklist | grep -c -E "sd-server|sd-cli|llama|yue")
[ "$n" != "0" ] && { echo "GPU busy: $n"; exit 1; }
"$P" _tools/yue.py start || exit 1
for req in $("$P" _tools/mkreq.py "$1" | tr -d '\r'); do
  b=$(basename "$req" .json)
  [ -f "20_audio/cand/${b}_1.mp3" ] && continue
  echo "== $b $(date +%T)"
  "$P" _tools/yue.py gen "$req" "20_audio/cand/$b"
done
"$P" _tools/yue.py stop
echo "ALL DONE $(date +%T)"
