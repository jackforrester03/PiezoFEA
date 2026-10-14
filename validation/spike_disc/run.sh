#!/bin/sh
# Spike runner (inside the backend container): build mesh + materials, run each case in
# its own run dir under /data/runs/spike_disc/<case>, and record wall time.
# Usage: sh run.sh [case ...]   (default: all cases)
set -e
SRC=$(cd "$(dirname "$0")" && pwd)
OUT=/data/runs/spike_disc
CASES=${*:-"eigen_short eigen_open harm_wide harm_radial harm_fr_fine"}
mkdir -p "$OUT"
python "$SRC/make_mesh.py" "$OUT/disc.msh"
python "$SRC/make_mat.py" "$OUT/mat.xml"
python "$SRC/make_mat.py" "$OUT/mat_lossless.xml" --lossless
for c in $CASES; do
  d="$OUT/$c"
  rm -rf "$d" && mkdir -p "$d"
  cp "$SRC/$c.xml" "$OUT/disc.msh" "$OUT/mat.xml" "$OUT/mat_lossless.xml" "$d/"
  echo "== $c"
  start=$(date +%s)
  (cd "$d" && cfs -t "$(nproc)" -p "$c.xml" "$c" > cfs.log 2>&1) || { echo "FAILED, see $d/cfs.log"; tail -20 "$d/cfs.log"; exit 1; }
  echo "   done in $(( $(date +%s) - start )) s"
done
