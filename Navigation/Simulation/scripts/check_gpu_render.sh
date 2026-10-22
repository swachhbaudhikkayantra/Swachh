#!/usr/bin/env bash
# check_gpu_render.sh - check whether Mesa d3d12 (WSL2 GPU) rendering works.
#
# Usage:
#   check_gpu_render.sh [--gz WORLD.sdf] [--adapter NAME] [--secs N]
#     --gz WORLD     also run a headless gz server on WORLD with/without the
#                    GPU env vars and measure TRUE RTF = d(sim_time)/d(wall)
#     --adapter NAME MESA_D3D12_DEFAULT_ADAPTER_NAME (default: Intel)
#     --secs N       measurement window per gz run (default: 60)
#   Starts nothing ROS-related. Only the gz process group it starts is killed.
set -u

WORLD=""
ADAPTER="Intel"
SECS=60
while [ $# -gt 0 ]; do
  case "$1" in
    --gz) WORLD="${2:-}"; shift 2 ;;
    --adapter) ADAPTER="${2:-}"; shift 2 ;;
    --secs) SECS="${2:-60}"; shift 2 ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

renderer() {  # prints the OpenGL renderer string, run with the env given as args
  if command -v glxinfo >/dev/null 2>&1; then
    env "$@" glxinfo -B 2>/dev/null | grep -i "OpenGL renderer" | head -1
  elif command -v eglinfo >/dev/null 2>&1; then
    env "$@" eglinfo 2>/dev/null | grep -i "OpenGL core profile renderer" | head -1
  else
    echo "(glxinfo/eglinfo not installed: sudo apt install mesa-utils)"
  fi
}

R_DEF=$(renderer A=1)
R_GPU=$(renderer GALLIUM_DRIVER=d3d12 "MESA_D3D12_DEFAULT_ADAPTER_NAME=$ADAPTER")
echo "default : ${R_DEF:-none}"
echo "d3d12   : ${R_GPU:-none}"
D3D_ACTIVE=no
case "$R_GPU" in *[Dd]3[Dd]12*|*Intel*|*NVIDIA*|*AMD*) D3D_ACTIVE=yes ;; esac
case "$R_GPU" in *llvmpipe*) D3D_ACTIVE=no ;; esac

if [ -z "$WORLD" ]; then
  echo "VERDICT: d3d12 renderer active=$D3D_ACTIVE (no gz RTF test; pass --gz WORLD)"
  exit 0
fi
[ -f "$WORLD" ] || { echo "world not found: $WORLD" >&2; exit 2; }
command -v gz >/dev/null 2>&1 || { echo "gz not found" >&2; exit 2; }

# sim time in seconds from one /stats message
sim_time() {
  timeout 5 gz topic -e -n 1 -t /stats 2>/dev/null | awk '
    /sim_time/ {f=1} f&&/sec:/ {s=$2} f&&/nsec:/ {n=$2; print s+n/1e9; exit}'
}

run_rtf() {  # args: env assignments...; prints true RTF
  setsid env "$@" gz sim -r -s --headless-rendering "$WORLD" >/dev/null 2>&1 &
  local pid=$! t0 t1 w0 w1
  sleep 15   # let the server load
  t0=$(sim_time); w0=$(date +%s.%N)
  sleep "$SECS"
  t1=$(sim_time); w1=$(date +%s.%N)
  kill -- "-$pid" 2>/dev/null
  wait "$pid" 2>/dev/null
  if [ -z "$t0" ] || [ -z "$t1" ]; then echo "nan"; return; fi
  awk -v a="$t0" -v b="$t1" -v c="$w0" -v d="$w1" 'BEGIN{printf "%.3f", (b-a)/(d-c)}'
}

echo "running gz without GPU env (${SECS}s)..."
RTF_DEF=$(run_rtf A=1)
sleep 3
echo "running gz with GALLIUM_DRIVER=d3d12 (${SECS}s)..."
RTF_GPU=$(run_rtf GALLIUM_DRIVER=d3d12 "MESA_D3D12_DEFAULT_ADAPTER_NAME=$ADAPTER")

SPEEDUP=$(awk -v a="$RTF_DEF" -v b="$RTF_GPU" 'BEGIN{ if (a+0>0 && b+0>=0) printf "%.2f", b/a; else print "nan"}')
echo "VERDICT: true RTF default=$RTF_DEF d3d12=$RTF_GPU speedup=${SPEEDUP}x d3d12 renderer active=$D3D_ACTIVE"
