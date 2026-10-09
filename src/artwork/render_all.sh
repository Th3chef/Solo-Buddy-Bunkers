#!/bin/sh
# renders the four scene shots (about an hour on 2 CPU cores)
cd "$(dirname "$0")"
PY=${BPY:-python3}
for shot in "square 1254 1254" "wide 1920 1080" "social 1280 640" "header 1300 372"; do
  set -- $shot
  $PY scene.py renders/$1.png $2 $3 $1 64 > renders/$1.log 2>&1
done
echo done > renders/DONE
