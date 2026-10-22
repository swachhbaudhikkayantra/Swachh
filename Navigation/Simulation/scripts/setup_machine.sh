#!/usr/bin/env bash
# Machine setup for the Swachh vacuum evaluation (WSL2 or native Ubuntu).
# Usage: setup_machine.sh [--dry-run] [--yes]
set -u
DRY=0; YES=0
for a in "$@"; do case "$a" in --dry-run) DRY=1;; --yes|-y) YES=1;; *) echo "unknown arg $a"; exit 2;; esac; done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIM_DIR="$(dirname "$SCRIPT_DIR")"
REPO="$(cd "$SIM_DIR/../.." && pwd)"
WS="$SIM_DIR/vacuum_ws"
CYCLONE="$REPO/Navigation/cyclone_dds.xml"
STEP=0
step() { STEP=$((STEP+1)); echo; echo "=== [$STEP] $* ==="; }
run() { if [ $DRY -eq 1 ]; then echo "[dry-run] $*"; else echo "+ $*"; "$@"; fi; }
SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"
[ $DRY -eq 1 ] && echo "DRY RUN: nothing will be changed."

confirm() {
  [ $DRY -eq 1 ] && return 0
  [ $YES -eq 1 ] && return 0
  read -r -p "$1 [y/N] " r; [[ "$r" =~ ^[Yy] ]]
}

step "Detect platform"
IS_WSL=0; grep -qi microsoft /proc/version 2>/dev/null && IS_WSL=1
. /etc/os-release 2>/dev/null
echo "OS: ${PRETTY_NAME:-unknown} (codename ${VERSION_CODENAME:-?}); WSL=$IS_WSL"
echo "Repo: $REPO"; echo "Workspace: $WS"
if [ "${VERSION_ID:-}" != "24.04" ]; then
  echo "WARNING: ROS 2 Jazzy binaries target Ubuntu 24.04. On ${VERSION_ID:-this OS} (e.g. 26.04) the apt packages"
  echo "         may be unavailable; use a 24.04 install/container, or a newer ROS distro (not validated here)."
fi
if [ -d /opt/ros/jazzy ]; then echo "ROS Jazzy: present"; else
  echo "ROS Jazzy: NOT found in /opt/ros/jazzy. Add the ROS apt repo first:"
  echo "  https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html"
  [ $DRY -eq 0 ] && { echo "Aborting."; exit 1; }
fi

step "GPU"
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi --query-gpu=name,driver_version --format=csv,noheader || true
  echo "Gazebo will use the GPU natively; keep render_gpu=false (that flag is only for WSL d3d12)."
else
  echo "nvidia-smi not found: software rendering (llvmpipe) will be used. Slow but works."
fi

step "apt packages"
PKGS=(ros-jazzy-desktop ros-jazzy-ros-gz ros-jazzy-gz-ros2-control ros-jazzy-ros2-control
  ros-jazzy-ros2-controllers ros-jazzy-navigation2 ros-jazzy-nav2-bringup ros-jazzy-rtabmap-ros
  ros-jazzy-depthimage-to-laserscan ros-jazzy-topic-tools ros-jazzy-rmw-cyclonedds-cpp
  ros-jazzy-spatio-temporal-voxel-layer python3-psutil python3-scipy python3-matplotlib
  python3-pil python3-yaml python3-pytest mesa-utils python3-colcon-common-extensions python3-rosdep)
MISSING=()
for p in "${PKGS[@]}"; do dpkg -s "$p" >/dev/null 2>&1 || MISSING+=("$p"); done
if [ ${#MISSING[@]} -eq 0 ]; then echo "All packages already installed."; else
  echo "Missing: ${MISSING[*]}"
  if confirm "Install with apt (sudo)?"; then run $SUDO apt-get update; run $SUDO apt-get install -y "${MISSING[@]}"; else echo "Skipped."; fi
fi

step "DDS socket buffers (sysctl)"
SYSCTL=/etc/sysctl.d/90-ros2-dds.conf
CONTENT=$'net.core.rmem_max=33554432\nnet.core.rmem_default=33554432\nnet.core.wmem_max=33554432\nnet.core.wmem_default=33554432'
if [ -f "$SYSCTL" ] && [ "$(cat "$SYSCTL")" = "$CONTENT" ]; then echo "$SYSCTL up to date."; else
  if [ $DRY -eq 1 ]; then echo "[dry-run] write $SYSCTL"; else printf '%s\n' "$CONTENT" | $SUDO tee "$SYSCTL" >/dev/null; fi
fi
run $SUDO sysctl -p "$SYSCTL"
if [ $IS_WSL -eq 1 ]; then
  echo "WSL: ensuring /etc/wsl.conf [boot] command reapplies sysctl."
  if grep -q "sysctl" /etc/wsl.conf 2>/dev/null; then echo "already present."; elif [ $DRY -eq 1 ]; then
    echo "[dry-run] append [boot] command to /etc/wsl.conf"
  else
    if grep -q '^\[boot\]' /etc/wsl.conf 2>/dev/null; then
      $SUDO sed -i '/^\[boot\]/a command = sysctl -p /etc/sysctl.d/90-ros2-dds.conf' /etc/wsl.conf
    else
      printf '\n[boot]\ncommand = sysctl -p /etc/sysctl.d/90-ros2-dds.conf\n' | $SUDO tee -a /etc/wsl.conf >/dev/null
    fi
    echo "Added. Takes effect after 'wsl --shutdown'."
  fi
else
  echo "Native Linux: /etc/sysctl.d is applied at boot automatically."
fi

step "~/.bashrc"
add_line() { grep -qxF "$1" ~/.bashrc 2>/dev/null && echo "present: $1" || { if [ $DRY -eq 1 ]; then echo "[dry-run] append: $1"; else echo "$1" >> ~/.bashrc; echo "added: $1"; fi; }; }
add_line "source /opt/ros/jazzy/setup.bash"
add_line "[ -f $WS/install/setup.bash ] && source $WS/install/setup.bash"
add_line "export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp"
add_line "export CYCLONEDDS_URI=file://$CYCLONE"

step "rosdep"
if [ -d /opt/ros/jazzy ]; then
  [ -f /etc/ros/rosdep/sources.list.d/20-default.list ] || run $SUDO rosdep init
  run rosdep update
  if confirm "rosdep install (sudo, apt)?"; then
    run bash -c "source /opt/ros/jazzy/setup.bash && cd '$WS' && rosdep install --from-paths src --ignore-src -r -y"
  fi
fi

step "colcon build"
run bash -c "source /opt/ros/jazzy/setup.bash && cd '$WS' && colcon build --symlink-install"

step "vacuum_eval unit tests"
run bash -c "source /opt/ros/jazzy/setup.bash && source '$WS/install/setup.bash' && cd '$WS/src/vacuum_eval' && python3 -m pytest -q"

echo; echo "Done. Open a new shell (or source ~/.bashrc), then run: $SCRIPT_DIR/preflight.sh"
