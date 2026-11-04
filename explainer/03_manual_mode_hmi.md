# Manual Mode: GTK4 HMI and Arduino firmware

Scope: every file under `/home/hrishikesh/Swachh/Navigation/Manual mode/` (note the space in the directory name; quote it in shell commands). This document describes only what the code does.

## 1. High-level overview

Manual mode is a teleoperation path that is independent of ROS and of the simulation evaluation. It has two programs:

| Part | Where | Language | Runs on | Role |
|---|---|---|---|---|
| HMI (operator GUI) | `hmi/` | C++17, GTK4 | The robot's computer (README says Jetson Orin Nano; `claude_context.md` says Raspberry Pi 5; `main.cpp` comment says "RPi default") | Fullscreen touchscreen window. Operator presses buttons; the HMI sends text commands over USB serial and logs everything. |
| Motor controller firmware | `arduino/swacch_robot/swacch_robot.ino` | Arduino C++ | Arduino connected by USB | Parses commands, drives two motor throttle (PWM) pins and two direction relay pins, replies `ACK:`/`ERR:`, and prints a `STATUS:` line every second. |

How an operator drives the robot:

1. Start the HMI (`hmi/scripts/run.sh`). It opens the serial port to the Arduino at 115200 baud.
2. The window shows status, battery, telemetry, an EMERGENCY STOP and Reset button, component toggles (Vacuum, Arm, Wiper, UV, Auto), nine speed buttons, and a D-pad (Forward, Left, STOP, Right, Backward).
3. Movement is "hold to move": pressing a direction button sends `MOVE:<DIR>`; releasing it sends `MOVE:STOP`.
4. Every command is a single ASCII line ending in `\n`. The Arduino answers with `ACK:<command>` or an `ERR:` line.

Only the motors have real hardware behind them in the firmware. Vacuum, arm, wiper and UV are software flags only (see section 6).

## 2. Directory contents

| Path | What it is |
|---|---|
| `README.md` | Short project description, setup/run commands, one-paragraph protocol summary. |
| `claude_context.md` | Older project-context note (vision pipeline on a Raspberry Pi 5, Distrobox ROS 2, etc.). Mostly not about this HMI; see section 9. |
| `ros.sh` | Enters Distrobox container `ros-dev` and sources `/opt/ros/humble/setup.bash`. Unrelated to the HMI code. |
| `stats.sh` | Prints RPi temperature, CPU, RAM, disk. Unrelated to the HMI code. |
| `hmi/CMakeLists.txt` | Build definition. |
| `hmi/scripts/setup.sh` | Installs dependencies, adds user to `dialout`. |
| `hmi/scripts/run.sh` | Builds if needed, auto-detects serial port, launches the HMI. |
| `hmi/include/system_state.hpp` | `SystemState` struct (HMI-side state). |
| `hmi/include/serial_comm.hpp`, `hmi/src/serial_comm.cpp` | `SerialComm` class (POSIX serial port). |
| `hmi/include/logger.hpp`, `hmi/src/logger.cpp` | `Logger` class (4-category console and file logging). |
| `hmi/include/gui.hpp`, `hmi/src/gui.cpp` | `Widgets` struct, window layout, CSS, display-update helpers, timer registration. |
| `hmi/include/callbacks.hpp`, `hmi/src/callbacks.cpp` | Button handlers, movement state, serial-poll and battery timers. |
| `hmi/src/main.cpp` | Entry point, CLI parsing, `g_system_state` definition. |
| `arduino/swacch_robot/swacch_robot.ino` | Firmware. |

## 3. Build and run

### Setup (once)
`bash hmi/scripts/setup.sh` runs: `sudo apt update`, `sudo apt install -y build-essential cmake pkg-config libgtk-4-dev`; installs `arduino-cli` via its install script if absent; `sudo usermod -a -G dialout $USER`. It then asks the user to reboot or log out/in.

### Build
`hmi/CMakeLists.txt`: project `SwacchHMI_Final`, C++17, `pkg_check_modules(GTK4 REQUIRED gtk4)`, sources `src/main.cpp src/gui.cpp src/callbacks.cpp src/serial_comm.cpp src/logger.cpp`, executable `swacch_hmi`, compile options `-Wall -O2`, install rule to `bin`. Manual build:

```
cd "/home/hrishikesh/Swachh/Navigation/Manual mode/hmi"
mkdir -p build && cd build && cmake .. && make -j$(nproc)
```

### Run
`bash hmi/scripts/run.sh`:

1. If `hmi/build/swacch_hmi` does not exist, creates `hmi/build`, runs `cmake ..` and `make -j$(nproc)`. If the binary exists it skips the build (it does not rebuild after source edits).
2. Picks the first existing path from the glob `/dev/ttyUSB* /dev/ttyACM*` (the USB glob is checked first).
3. If none exist, prints an error but continues with `PORT=/dev/ttyUSB0`.
4. `exec`s `swacch_hmi --port "$PORT"`.

Command-line options of `swacch_hmi` (parsed in `main.cpp`):

| Option | Default | Meaning |
|---|---|---|
| `--port <path>` | `/dev/ttyUSB0` | Serial device. |
| `--log-dir <path>` | `logs` (relative to the current working directory) | Base directory for log files. |

### Flashing the firmware
`setup.sh` installs `arduino-cli` "optionally, for uploading firmware", but no script in this folder compiles or uploads `swacch_robot.ino`, and the board type is not stated anywhere. Flash it with your own Arduino tooling.

## 4. Serial protocol

Link: 115200 baud, 8 data bits, no parity, 1 stop bit, no flow control. Commands are ASCII lines. The Arduino treats `\n` or `\r` as the terminator, trims the line, and upper-cases it, so case does not matter on the Arduino side. Maximum command length is 64 characters (`CMD_BUFFER_SIZE`); a longer line makes the Arduino clear its buffer and print `ERR:CMD_TOO_LONG`.

### Commands the Arduino understands, and whether the HMI ever sends them

| Command | Arduino behaviour | Sent by HMI? |
|---|---|---|
| `MOVE:FORWARD` | Stop motors, wait 50 ms, set both relays HIGH, wait 50 ms, set PWM for current speed on both throttles. Replies `ACK:MOVE:FORWARD`. | Yes (Forward button press) |
| `MOVE:BACKWARD` | Same, both relays LOW. | Yes (Backward) |
| `MOVE:LEFT` | Tank turn: left relay LOW, right relay HIGH. | Yes (Left) |
| `MOVE:RIGHT` | Tank turn: left relay HIGH, right relay LOW. | Yes (Right) |
| `MOVE:STOP` | PWM 0 on both throttles, `moving=false`. | Yes (button release, STOP button) |
| `SPEED:<n>` | If `n` is 1 to 9: sets `speed_level`; if moving, updates PWM at once. Any other value (including non-numeric, which `toInt()` gives as 0) is ignored but still ACKed. | Yes, `SPEED:1` to `SPEED:9` |
| `VACUUM:ON` / `VACUUM:OFF` | Sets a flag only; ACK. | Yes |
| `ARM:ON` / `ARM:OFF` | Sets a flag only; ACK. | Yes |
| `WIPER:ON` / `WIPER:OFF` | Sets a flag only; ACK. | Yes |
| `UV:ON` / `UV:OFF` | Sets a flag only; ACK. | Yes |
| `AUTO:ON` | Sets `autonomous_mode=true`; ACK. | Yes (Auto button) |
| `AUTO:OFF` | Sets `autonomous_mode=false`, stops motors; ACK. | Yes (Auto button) |
| `AI:ON` / `AI:OFF` | ACK only, no state change. | No. The HMI has `ai_detection` in `SystemState` but no button or call uses it. |
| `ESTOP` | Sets `emergency_stop`, stops motors, clears the vacuum/arm/wiper/UV/auto flags; ACK. | Yes |
| `RESET` | Clears `emergency_stop`, stops motors; ACK. | Yes |
| anything else | `ERR:UNKNOWN_CMD:<UPPERCASED CMD>` | n/a |

Unsupported or never-sent commands:

- `ARM:PICK <X>,<Y>,<Z>` is described in `claude_context.md` (section 3.A step 4) as sent by a Python `serial_comm.py`. The firmware has no handler for it: it would hit the "unknown command" branch and reply `ERR:UNKNOWN_CMD:ARM:PICK ...`. The files in `Manual mode/` contain no Python and no code that sends it.
- The README's "`MOVE:FORWARD`, `MOVE:LEFT`, etc." matches the code; the backward command is spelled `MOVE:BACKWARD` (not `BACK`).
- `AI:ON` / `AI:OFF` are accepted by the firmware but never sent.
- The firmware has no command to read status on demand; status only arrives periodically.

### Replies from the Arduino

| Line | When |
|---|---|
| `SWACCH:READY` | Once at boot, after `Serial.begin`. |
| `ACK:<CMD>` | After each handled command (the command echoed in upper case, trimmed). |
| `ERR:EMERGENCY_STOP_ACTIVE` | Any command other than `ESTOP`/`RESET` while the e-stop flag is set. |
| `ERR:UNKNOWN_CMD:<CMD>` | Unrecognised command. |
| `ERR:CMD_TOO_LONG` | Line longer than 64 characters. |
| `STATUS:VAC=0,ARM=0,WPR=0,UV=0,AUTO=0,ESTOP=0,MOVE=0,SPD=5,PWM=0` | Every time more than `STATUS_INTERVAL` (1000 ms) has passed since the last one, checked at the end of `loop()`. Fields are 0/1 flags, `SPD` is 1 to 9, `PWM` is the current PWM value. |

### Speed table (firmware `SPEED_PWM`)

| Level | 1 | 2 | 3 | 4 | 5 (default) | 6 | 7 | 8 | 9 |
|---|---|---|---|---|---|---|---|---|---|
| PWM | 80 | 102 | 124 | 146 | 168 | 190 | 212 | 234 | 255 |

The header comment at the top of the `.ino` lists a different mapping (28, 57, 85, ... 255) which does not match the actual table; the table in the code is what runs.

## 5. Firmware in detail (`arduino/swacch_robot/swacch_robot.ino`)

Pins:

| Signal | Pin |
|---|---|
| Left motor throttle (PWM) `throttlePin1` | 5 |
| Left motor direction relay `relayPin1` | 7 |
| Right motor throttle (PWM) `throttlePin2` | 6 |
| Right motor direction relay `relayPin2` | 8 |

Global state: struct `state` with `vacuum_active, arm_active, wiper_active, uv_active, autonomous_mode, emergency_stop, moving, speed_level, current_pwm`; `String commandBuffer`; `unsigned long lastStatusUpdate`.

Functions:

| Function | What it does |
|---|---|
| `stopMotors()` | `analogWrite(…,0)` on both throttles; `moving=false`; `current_pwm=0`. Relays are not touched. |
| `applySpeed()` | `current_pwm = SPEED_PWM[speed_level]` if `moving`, else 0. |
| `moveForward()`, `moveBackward()`, `turnLeft()`, `turnRight()` | Each: `stopMotors()`; `delay(50)`; set both relays; `delay(50)`; `moving=true`; `applySpeed()`; write PWM to both throttles. Direction changes therefore always pass through a 100 ms zero-throttle window (blocking `delay`s) before power is re-applied. |
| `sendAck(cmd)` | Prints `ACK:` + cmd + newline. |
| `processCommand(cmd)` | Trim, upper-case, ignore empty. Order of checks: `ESTOP`, `RESET`, then the e-stop gate (`ERR:EMERGENCY_STOP_ACTIVE`), then the command table in section 4. |
| `sendStatusUpdate()` | Prints the `STATUS:` line. |
| `setup()` | Pins as outputs, `stopMotors()`, all flags false, `speed_level=5`, `Serial.begin(115200)`, waits `while(!Serial)`, prints `SWACCH:READY`. Relay pins are not explicitly driven in `setup()`. |
| `loop()` | Reads all available serial bytes into `commandBuffer`, dispatches on `\n`/`\r`, then emits `STATUS:` if due. |

Safety behaviour in the firmware (as coded):

- E-stop latches until `RESET`; while latched all other commands get `ERR:EMERGENCY_STOP_ACTIVE`.
- `ESTOP` and `RESET` stop motors (throttle to 0). `RESET` does not restore the peripheral flags.
- There is no heartbeat or command timeout: if the HMI dies or the cable is unplugged while a direction is active, the firmware keeps the last command running. The only stop sources are `MOVE:STOP`, `ESTOP`, `RESET`, `AUTO:OFF`, or power cycle.
- The firmware does not refuse `MOVE:*` while `autonomous_mode` is true; that check exists only in the HMI.
- There is no hardware current limiting, ramping or end-stop logic.

## 6. HMI in detail

### `hmi/include/system_state.hpp`
`struct SystemState` with defaults: `vacuum_active, arm_active, wiper_active, uv_active, autonomous_mode, emergency_stop` false; `ai_detection` true (never used elsewhere); `moving` false; `battery_level` 100; `speed_level` 5; `status` "System Ready". The single instance `g_system_state` is defined in `main.cpp`. The HMI state is its own copy; it is not updated from the Arduino's `STATUS:` lines.

### `hmi/src/main.cpp`
- Parses `--port` and `--log-dir`.
- `g_logger.init(log_dir)`, logs a banner and the port/log directory.
- `g_serial.connect(port)`. On success: sleeps 1500 ms (lets an Arduino finish its auto-reset), then `read_response(500)` and logs the startup line (normally `SWACCH:READY`) under the ARDUINO category. On failure it logs an error and continues: the GUI still opens without hardware.
- Creates `GtkApplication` id `com.swacch.hmi.final`; `activate` calls `create_hmi_interface`. It passes `argc=1` to `g_application_run` so the custom arguments are not seen by GTK.
- After the main loop ends: `g_serial.disconnect()`, `g_object_unref(app)`. Note: nothing sends `MOVE:STOP` or `ESTOP` on shutdown.

### `hmi/src/serial_comm.cpp` (class `SerialComm`, global `g_serial`)

| Member | Behaviour |
|---|---|
| `connect(port)` | `open(O_RDWR \| O_NOCTTY \| O_NONBLOCK)`; configures termios: 115200 in/out, 8N1, no hardware/software flow control, raw (no ICANON/ECHO/ISIG, no output post-processing, no CR/LF translation), `VTIME=1`, `VMIN=0`; `tcflush(TCIOFLUSH)`; sets `connected=true`. On a `tcgetattr`/`tcsetattr` failure it returns false without closing the descriptor. |
| `send_command(cmd)` | Fails (returns false, logs) if not connected. Otherwise writes `cmd + "\n"`, `tcdrain`, then calls `read_response(500)` and logs the single line it gets: `ACK:` as SUCCESS, `ERR:` as ERROR, `STATUS:` as INFO, anything else as INFO; empty means logs "No response (timeout 500ms)" as ERROR. It returns true whenever the write succeeded, even if the reply was an `ERR:` or missing. The reply read is not matched to the command: if a periodic `STATUS:` line arrives first it is consumed here instead of the ACK. |
| `read_response(timeout_ms)` | Polls one byte at a time, sleeping 5 ms when no data, returns the first non-empty line (terminated by `\n` or `\r`), or whatever partial text was collected at timeout. |
| `read_nonblocking()` | Reads bytes until none are available; returns the first complete non-empty line, or a partial line if data ran out mid-line (partial bytes are not kept for the next call). |
| `is_connected()`, `disconnect()` | Close descriptor and clear flag. |

Timing consequence: `send_command` runs on the GTK main thread and can block the UI for up to 500 ms per command (the firmware's two 50 ms delays plus ACK transit normally make it much shorter).

### `hmi/src/logger.cpp` (class `Logger`, global `g_logger`)
- Categories and meaning: `HMI` (button presses), `JETSON` (HMI-side command processing; the name is historical), `ARDUINO` (replies), `COMM` (serial TX/RX). Levels: `INFO`, `SUCCESS`, `ERROR`.
- `init(base)` creates `base`, `base/hmi`, `base/jetson`, `base/arduino`, `base/communication` (single-level `mkdir`, mode 0755; the parent of `base` must exist) and opens (append mode) `base/hmi/hmi_<YYYY-MM-DD>.log`, `base/jetson/jetson_<date>.log`, `base/arduino/arduino_<date>.log`, `base/communication/comm_<date>.log`. Files are opened once at start; the date in the name is not rolled over at midnight.
- `log()` is mutex-protected. It prints a coloured line to stdout `[HH:MM:SS.mmm] [CATEGORY] [LEVEL] message` and writes the plain line `[HH:MM:SS.mmm] [LEVEL] message` to the category file, flushing every line.

### `hmi/src/gui.cpp`
Globals: `Widgets g_widgets` (pointers listed in `gui.hpp`), `SPEED_NAMES` ("1: Crawl" ... "9: Max").

| Function | Behaviour |
|---|---|
| `update_status()` | Sets the status label to `g_system_state.status` and the battery label to `Battery: N%`. |
| `update_speed_buttons()` | Adds CSS class `speed-active` to the button for the current level, removes it from others; updates "Speed Level: n / 9". |
| `update_telemetry()` | Shows Arduino Connected/Disconnected (from `g_serial.is_connected()`), Motors MOVING/IDLE (from HMI state, not the Arduino), and ON/off for Vacuum, Arm, Wiper, UV (HMI state). |
| `apply_css()` | Dark theme CSS (window `#1a1a2e`, styled buttons, classes `destructive-action`, `suggested-action`, `speed-active`). |
| `create_hmi_interface(app)` | Builds a fullscreen (`gtk_window_fullscreen`, default size 820x750) scrollable window. Layout top to bottom: title, status label, battery label, Telemetry frame, EMERGENCY STOP (240x50) plus Reset (100x50), Component Controls (Vacuum, Arm, Wiper, UV in one row; Auto below), Speed Level grid (3x3 of nine buttons), Movement Controls ("hold to move": Forward top, Left/STOP/Right middle, Backward bottom). Registers two timers: `g_timeout_add(50, serial_poll_tick)` (20 Hz) and `g_timeout_add_seconds(5, battery_tick)`. |

Movement buttons use a `GtkGestureClick` in the CAPTURE phase with `pressed` bound to `on_move_pressed` (direction passed as `GINT_TO_POINTER(dir)`) and `released` bound to `on_move_released`. The STOP button uses a normal `clicked` signal to `on_stop`. The function `on_move_cancelled` / `GtkGestureClick "cancel"` is declared and defined but no code connects it to a signal.

### `hmi/src/callbacks.cpp`
`MoveDir` enum (`DIR_NONE, DIR_FWD, DIR_BWD, DIR_LEFT, DIR_RIGHT`) and global `g_move_dir`.

| Function | Behaviour |
|---|---|
| `stop_movement()` | `g_move_dir=DIR_NONE`; sends `MOVE:STOP`; status "Stopped"; `moving=false`; refreshes status. Has no e-stop guard. |
| `on_move_pressed` | Returns without sending if `emergency_stop` or `autonomous_mode` is set (logs an ERROR). Otherwise sets `g_move_dir`, sends `MOVE:FORWARD/BACKWARD/LEFT/RIGHT`, sets status "Moving <Dir>" and `moving=true`. |
| `on_move_released`, `on_move_cancelled` | Call `stop_movement()`. Because `on_move_released` is bound to every direction button, a release always sends `MOVE:STOP`, even if the press was blocked (e-stop or auto mode). |
| `on_stop` | Ignored while e-stop is set; otherwise logs and `stop_movement()`. |
| `on_estop` | Sets HMI e-stop, clears all four peripheral flags, auto mode, `moving`, `g_move_dir`; status "EMERGENCY STOP"; sends `ESTOP`; resets the five toggle button labels (Vacuum, Arm, Wiper, UV, Auto). Not guarded: always works. |
| `on_reset` | Clears HMI e-stop, status "System Ready", sends `RESET`. The peripheral flags stay off. |
| `on_vacuum`, `on_arm`, `on_wiper`, `on_uv` | Blocked while e-stop. Otherwise toggle the HMI flag, set the button label to e.g. "Vacuum [ON]" or "Vacuum", send `<NAME>:ON` or `<NAME>:OFF`, set status text. |
| `on_auto_toggle` | Blocked while e-stop. Toggles `autonomous_mode`, sends `AUTO:ON`/`AUTO:OFF`, status "Autonomous Mode" or "Manual Mode". While auto mode is on, the HMI refuses to send movement. In this folder, "Auto" is only a flag: no code here performs autonomous driving. |
| `on_speed_select(data)` | `data` is the 0-based button index; sets `speed_level = index+1` and sends `SPEED:<n>`. Not blocked by e-stop (the Arduino would answer `ERR:EMERGENCY_STOP_ACTIVE`, and the HMI would still show the new level). |
| `parse_status(msg)` | Only logs the STATUS line; it does not parse fields or change HMI state. |
| `serial_poll_tick` (every 50 ms) | If connected, drains pending lines via `read_nonblocking()`, logging `STATUS:`, `ACK:`, `ERR:`, `SWACCH:` and other lines, then calls `update_telemetry()`. Always returns TRUE (timer repeats). |
| `battery_tick` (every 5 s) | Battery is simulated: decrements `battery_level` by 1 per tick while at least one of vacuum/arm/wiper/UV is active and level is above 0; then `update_status()`. It is not read from hardware and never increases. |

Safety behaviour summary (HMI side): hold-to-move with stop on release; e-stop blocks peripherals, auto toggle, STOP button and movement presses; the e-stop and Reset buttons are always active. The HMI has no watchdog and does not stop the motors if serial is lost; if disconnected, `send_command` just logs an error and the operator sees "Disconnected" in telemetry. The Arduino's e-stop state is not read back, so the HMI and Arduino can disagree (for example if the Arduino reboots).

## 7. Message flow example

Operator holds Forward, then releases:

1. `pressed` -> `on_move_pressed(DIR_FWD)` -> `SerialComm::send_command("MOVE:FORWARD")` writes `MOVE:FORWARD\n`.
2. Arduino: `stopMotors()`, 50 ms, relays HIGH, 50 ms, PWM = `SPEED_PWM[speed_level]` (168 at default level 5) on pins 5 and 6; prints `ACK:MOVE:FORWARD`.
3. HMI logs the ACK, status label shows "Moving Forward", telemetry shows MOVING.
4. `released` -> `stop_movement()` -> `MOVE:STOP\n` -> Arduino zeroes both throttles -> `ACK:MOVE:STOP`.

## 8. Logs

Default location `logs/` under the working directory the HMI is started from (`run.sh` does not change directory, so it is the directory you launch from). Subdirectories: `hmi/`, `jetson/`, `arduino/`, `communication/`, one file per day per category as listed in section 6.

## 9. Known issues and inconsistencies (as present in the code)

- `claude_context.md` describes a Raspberry Pi 5 / Python vision pipeline and a `vision/` directory that do not exist under `Manual mode/`; `README.md` describes a Jetson Orin Nano. The code itself does not identify the hardware.
- `README.md` lists structure as `src/ include/ arduino/ scripts/` at the top level; in the actual tree these are under `hmi/` (except `arduino/`, which is at the `Manual mode/` level).
- Vacuum, arm, wiper and UV have no output pins in the firmware (comment: "no dedicated pins, just track state for HMI"). Pressing them changes only firmware flags and the HMI display; no physical device is actuated by this code.
- Firmware header comment for speed-to-PWM is outdated versus the real table.
- `ai_detection` and the `AI:ON/OFF` command are unused by the HMI.
- `ARM:PICK` is not implemented in the firmware.
- ACK reading is not correlated to commands (section 6, `send_command`).
- `run.sh` skips rebuilding if the binary exists.
- No automated tests exist in this folder.

One-line summary: Manual mode is a fullscreen GTK4 C++ HMI that sends newline-terminated text commands (MOVE, SPEED, VACUUM, ARM, WIPER, UV, AUTO, ESTOP, RESET) at 115200 baud to an Arduino sketch that drives two PWM+relay motors for real and tracks the four peripheral commands as flags only, with hold-to-move and e-stop but no watchdog or timeout.
