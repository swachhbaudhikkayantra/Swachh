#!/usr/bin/env bash
# Step 3a: save the map that ./explore.sh has built. Run it WHILE exploration is still running.
# Usage: ./savemap.sh [world]      default: office   -> ~/maps/stage5/<world>.yaml/.pgm
# An existing map of the same name is renamed with a timestamp, never overwritten.
source "$(dirname "$0")/common.sh"
pick_world "${1:-office}"

OUT="$HOME/maps/stage5/$WORLD"
mkdir -p "$HOME/maps/stage5"
if [[ -e "$OUT.yaml" || -e "$OUT.pgm" ]]; then
    TS="$(date +%Y%m%d_%H%M%S)"
    for ext in yaml pgm; do
        [[ -e "$OUT.$ext" ]] && mv "$OUT.$ext" "$OUT.$TS.$ext.bak"
    done
    echo "[demo] Existing $WORLD map kept as $OUT.$TS.*.bak"
fi

ros2 run nav2_map_server map_saver_cli -f "$OUT" --ros-args -p use_sim_time:=true
if [[ -f "$OUT.yaml" && -f "$OUT.pgm" ]]; then
    echo "[demo] Saved: $OUT.yaml  (next: ./navigate.sh $WORLD)"
else
    echo "[demo] Map was NOT saved. Is ./explore.sh still running?"
    exit 1
fi
