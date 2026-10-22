#!/usr/bin/env bash
# Read-only checks to run before every evaluation batch. Never kills anything.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIM_DIR="$(dirname "$SCRIPT_DIR")"
REPO="$(cd "$SIM_DIR/../.." && pwd)"
WS="$SIM_DIR/vacuum_ws"
FAILS=0
pass() { echo "PASS  $*"; }
fail() { echo "FAIL  $*"; FAILS=$((FAILS+1)); }
info() { echo "INFO  $*"; }

R=$(cat /proc/sys/net/core/rmem_max 2>/dev/null)
[ "$R" = "33554432" ] && pass "rmem_max=33554432" || fail "rmem_max=$R (need 33554432: sudo sysctl -p /etc/sysctl.d/90-ros2-dds.conf)"

P=$(pgrep -fa "gz sim|ruby" | grep -v "pgrep" | grep -v "preflight.sh")
if [ -z "$P" ]; then pass "no stray gz sim / ruby processes"; else fail "stray processes (not killed):"; echo "$P" | sed 's/^/        /'; fi

mkdir -p "$HOME/eval_runs" 2>/dev/null
FREE=$(df -BG --output=avail "$HOME/eval_runs" 2>/dev/null | tail -1 | tr -dc '0-9')
[ -n "$FREE" ] && [ "$FREE" -ge 20 ] && pass "disk free ${FREE} GB under ~/eval_runs" || fail "disk free ${FREE:-?} GB (<20) under ~/eval_runs"

MEM=$(awk '/MemAvailable/{printf "%.1f", $2/1048576}' /proc/meminfo)
info "RAM available: ${MEM} GB"

if [ -n "${ROS_DISTRO:-}" ] && [ "$ROS_DISTRO" = "jazzy" ]; then pass "ROS env sourced (jazzy)"; else fail "ROS env not sourced (source /opt/ros/jazzy/setup.bash)"; fi
[ "${RMW_IMPLEMENTATION:-}" = "rmw_cyclonedds_cpp" ] && pass "RMW=rmw_cyclonedds_cpp" || fail "RMW_IMPLEMENTATION=${RMW_IMPLEMENTATION:-unset}"
[ -f "$WS/install/setup.bash" ] && pass "workspace built ($WS/install/setup.bash)" || fail "workspace not built (colcon build --symlink-install)"

CFG="${CYCLONEDDS_URI:-}"; CFG="${CFG#file://}"
[ -z "$CFG" ] && CFG="$REPO/Navigation/cyclone_dds.xml"
if [ -f "$CFG" ] && grep -Eq 'SocketReceiveBufferSize[^>]*min="(1[6-9]|[2-9][0-9])MB"' "$CFG"; then pass "CycloneDDS min receive buffer >=16MB ($CFG)"
else fail "CycloneDDS config missing or min buffer <16MB ($CFG); CYCLONEDDS_URI=${CYCLONEDDS_URI:-unset}"; fi

N=$(nproc); GPU=0; command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L >/dev/null 2>&1 && GPU=1
PAR=$(awk -v n="$N" 'BEGIN{p=int(n/6.5); if(p<1)p=1; print p}')
[ $GPU -eq 1 ] && PAR=$((PAR+1))
info "nproc=$N GPU=$GPU -> suggested --parallel $PAR (GPU offloads rendering; raise cautiously and check RTF)"

if command -v glxinfo >/dev/null 2>&1; then
  REN=$(glxinfo -B 2>/dev/null | grep -i "OpenGL renderer")
  if echo "$REN" | grep -qi llvmpipe; then fail "software rendering - slow ($REN)"; elif [ -n "$REN" ]; then pass "$REN"; else info "glxinfo gave no renderer (no display?)"; fi
else info "glxinfo not installed (apt install mesa-utils)"; fi

echo; [ $FAILS -eq 0 ] && echo "ALL CHECKS PASSED" || echo "$FAILS check(s) FAILED"
exit $((FAILS>0))
