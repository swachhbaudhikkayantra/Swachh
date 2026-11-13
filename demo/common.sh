# shellcheck shell=bash
# Shared setup for the demo scripts. Sourced by them; not run directly.

DEMO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$DEMO_DIR")"
NAV="$REPO/Navigation"
WS="$NAV/Simulation/vacuum_ws"
LOG_DIR="${SWACHH_DEMO_LOGS:-$HOME/.cache/swachh_demo}"
mkdir -p "$LOG_DIR"

if [[ ! -f $WS/install/setup.bash ]]; then
    echo "Workspace is not built: $WS/install/setup.bash is missing."
    echo "Build it:  cd $WS && source /opt/ros/jazzy/setup.bash && colcon build --symlink-install"
    exit 1
fi

# shellcheck disable=SC1091
source /opt/ros/jazzy/setup.bash
# shellcheck disable=SC1091
source "$WS/install/setup.bash"
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI="file://$NAV/cyclone_dds.xml"
export ROS_DOMAIN_ID=0

# No display (SSH): render headless so Gazebo does not crash. Only RViz is lost.
if [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
    export VACUUM_GZ_HEADLESS_RENDERING=1
    echo "[demo] No display found: Gazebo renders headless (no windows will open)."
fi

# README sec. 4: with a small socket buffer SLAM silently gets no camera images.
RMEM="$(cat /proc/sys/net/core/rmem_max 2>/dev/null || echo 0)"
if (( RMEM < 33554432 )); then
    echo "[demo] WARNING: net.core.rmem_max is $RMEM (need 33554432). SLAM may get no images."
    echo "       Fix: sudo sysctl -w net.core.rmem_max=33554432"
fi

# Worlds that sim.launch.py can select with world:=NAME (avoid_* need world_file, see avoid.sh).
WORLDS="apartment office corridor empty_room cluttered_room two_rooms_door multi_room_loop maze_dead_ends symmetric_hall"

# pick_world NAME  ->  sets WORLD, SX, SY (spawn). Spawn = first collision-checked candidate in
# vacuum_eval/config/worlds.yaml. Override with SPAWN_X / SPAWN_Y.
pick_world() {
    WORLD="${1:-office}"
    case " $WORLDS " in
        *" $WORLD "*) ;;
        *) echo "Unknown world '$WORLD'. Choose one of: $WORLDS"; exit 1 ;;
    esac
    case "$WORLD" in
        apartment)       SX=0;     SY=1 ;;
        two_rooms_door)  SX=-2;    SY=0 ;;
        multi_room_loop) SX=1.85;  SY=1.85 ;;
        *)               SX=0;     SY=0 ;;
    esac
    SX="${SPAWN_X:-$SX}"
    SY="${SPAWN_Y:-$SY}"
}

AVOID_WORLDS="avoid_u_trap avoid_dynamic_sudden avoid_dead_end avoid_narrow_gap avoid_narrow_gap_wide avoid_head_on avoid_cluster avoid_dynamic_cross"
RVIZ_CFG="$DEMO_DIR/demo.rviz"

# pick_any_world NAME -> like pick_world but also accepts avoid_* scenario worlds.
# Sets WORLD, SX, SY, WORLD_ARGS (launch args that select the world) and WORLD_DESC (one line).
pick_any_world() {
    local w="${1:-office}"
    if [[ " $AVOID_WORLDS " == *" $w "* ]]; then
        WORLD="$w"; SX=-2; SY=0
        [[ $w == avoid_dead_end ]] && SY=-1.2
        SX="${SPAWN_X:-$SX}"; SY="${SPAWN_Y:-$SY}"
        WORLD_ARGS=(world_file:="$WS/src/vacuum_gazebo/worlds/$w.sdf")
    else
        pick_world "$w"
        WORLD_ARGS=(world:="$WORLD")
    fi
    case "$WORLD" in
        office)               WORLD_DESC="desks, monitors, chairs, a plant: the main demo world (held-out test world)" ;;
        multi_room_loop)      WORLD_DESC="rooms joined in a loop: lets SLAM close loops (best coverage, 86%)" ;;
        maze_dead_ends)       WORLD_DESC="maze with dead ends: the hard case where the explorer stalled (14% coverage)" ;;
        two_rooms_door)       WORLD_DESC="two rooms and one doorway: navigation test world" ;;
        corridor)             WORLD_DESC="long featureless corridor" ;;
        symmetric_hall)       WORLD_DESC="identical pillars and plain walls on purpose: tests perceptual aliasing" ;;
        apartment)            WORLD_DESC="apartment: the world used for tuning" ;;
        cluttered_room)       WORLD_DESC="single cluttered room (development baseline)" ;;
        empty_room)           WORLD_DESC="single empty room (development baseline)" ;;
        avoid_u_trap)         WORLD_DESC="avoidance: static U-shaped trap between start and goal (paper: 3/3)" ;;
        avoid_dynamic_sudden) WORLD_DESC="avoidance: a box suddenly moves out from behind a wall (paper: 1/3)" ;;
        avoid_dead_end)       WORLD_DESC="avoidance: dead end" ;;
        avoid_narrow_gap*)    WORLD_DESC="avoidance: narrow gap between obstacles" ;;
        avoid_head_on)        WORLD_DESC="avoidance: obstacle head-on (development scenario)" ;;
        avoid_cluster)        WORLD_DESC="avoidance: cluster of obstacles (development scenario)" ;;
        avoid_dynamic_cross)  WORLD_DESC="avoidance: moving obstacle crosses the path (development scenario)" ;;
    esac
}

# start_rviz [extra rviz args]: demo RViz config in the background (needs a display).
start_rviz() {
    if [[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
        start_bg rviz ros2 run rviz2 rviz2 -d "$RVIZ_CFG" --ros-args -p use_sim_time:=true "$@"
    else
        echo "[demo] No display: RViz skipped."
    fi
}

# Refuse to start on top of a running simulation (two Gazebos on one DDS domain break each other).
require_clean() {
    if pgrep -u "$USER" -af '[g]z sim' >/dev/null; then
        echo "[demo] A Gazebo simulation is already running. Stop it first:  $DEMO_DIR/stop.sh"
        exit 1
    fi
}

# ---- background helpers (used by navigate.sh and manual.sh) ----
PIDS=()
# start_bg LOGNAME cmd args...  : run in its own process group so we can SIGINT the whole group.
start_bg() {
    local name="$1"; shift
    set -m
    "$@" >"$LOG_DIR/$name.log" 2>&1 &
    PIDS+=("$!")
    set +m
    echo "[demo] started $name (pid $!, log $LOG_DIR/$name.log)"
}

# Gentle shutdown: SIGINT to each group, wait up to 10 s, then SIGTERM. Never SIGKILL.
stop_bg() {
    local pid i
    for pid in "${PIDS[@]:-}"; do
        [[ -n "$pid" ]] && kill -INT -- "-$pid" 2>/dev/null || true
    done
    for i in $(seq 1 20); do
        local alive=0
        for pid in "${PIDS[@]:-}"; do
            [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null && alive=1
        done
        (( alive == 0 )) && break
        sleep 0.5
    done
    for pid in "${PIDS[@]:-}"; do
        [[ -n "$pid" ]] && kill -TERM -- "-$pid" 2>/dev/null || true
    done
}

# wait_for_topic TOPIC [SECONDS]
wait_for_topic() {
    local t="$1" n="${2:-60}" i
    for i in $(seq 1 "$n"); do
        if timeout 5 ros2 topic list 2>/dev/null | grep -qx "$t"; then return 0; fi
        sleep 1
    done
    echo "[demo] WARNING: topic $t did not appear within ${n}s (check $LOG_DIR/*.log)"
    return 1
}
