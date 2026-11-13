#!/usr/bin/env bash
# Manual mode on the REAL robot: the GTK4 touchscreen HMI talking to the Arduino over USB serial.
# Needs the Arduino plugged in (/dev/ttyUSB* or /dev/ttyACM*) and the HMI built (first run compiles it;
# needs cmake and GTK4, see Navigation/Manual mode/hmi/scripts/setup.sh).
# SAFETY: the firmware has NO command timeout and NO heartbeat: the last move command keeps running
#         until MOVE:STOP, ESTOP, RESET or power-off. Wheels off the ground for the first test,
#         e-stop within reach.
# Only the two drive motors are really wired; vacuum/arm/wiper/UV buttons only set flags.
HMI_DIR="$(cd "$(dirname "$0")/.." && pwd)/Navigation/Manual mode/hmi"
if ! ls /dev/ttyUSB* /dev/ttyACM* >/dev/null 2>&1; then
    echo "[hmi] No Arduino serial device found. The HMI will open without hardware (UI demo only)."
fi
if [[ ! -x "$HMI_DIR/build/swacch_hmi" ]]; then
    echo "[hmi] HMI not built yet; the first run compiles it (a minute or two)."
fi
echo "[hmi] Protocol: 115200 baud, MOVE:FORWARD/LEFT/STOP, SPEED:1..9, ESTOP, RESET (replies ACK:<cmd>)."
exec bash "$HMI_DIR/scripts/run.sh"
