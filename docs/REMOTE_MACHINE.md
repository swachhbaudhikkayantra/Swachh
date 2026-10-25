# Remote evaluation machine (facts as of 2026-10-25)

| Item | Value |
|---|---|
| Host | `victus` (a friend's PC), Tailscale IP `100.122.6.118` |
| User | `hrishikesh`, passwordless sudo (temporary; the owner removes it after the run) |
| OS | Ubuntu 24.04.4 LTS (kernel 7.0), Xorg session; no Docker fallback needed |
| GPU | NVIDIA RTX 5050 laptop GPU, 8 GB, 60 W cap, driver 595.91 (>= 570 needed) |
| CPU / RAM / disk | 16 threads / 22 GB / 88 GB free |
| Access | SSH key auth over Tailscale; VS Code Remote-SSH from the user's Windows laptop |

## Already done by the owner
openssh-server, tmux, git, curl, Tailscale, account, sudo, sleep/suspend masked. **Not yet done:** the repo clone, `setup_machine.sh`, preflight, anything ROS/Gazebo.

## Differences from the plan's assumptions
- The plan assumes an A6000-class GPU. This is a **60 W laptop GPU with 8 GB**: expect throttling. Check `rtf_true_mean` in A1 (gate G-SPEED) and watch `nvidia-smi -q -d PERFORMANCE`/temperature. Two parallel slots may not fit; fall back to serial per plan §7 if the gate says so.
- 22 GB RAM is enough for `--parallel 2` but not much more; do not run RViz or other heavy apps during the Phase C test campaign.
- The owner stays logged in to the desktop (Xorg), so headless rendering is normally NOT needed. If preflight reports llvmpipe instead of NVIDIA, set `VACUUM_GZ_HEADLESS_RENDERING=1` (plan §1.5).

## The user wants to watch the robot
Evaluation runs open no windows (headless Gazebo, RViz off). During **Phase A only**, the user may view on the desktop (via Remote Desktop/AnyDesk) by opening, in a terminal on that desktop:
```bash
source /opt/ros/jazzy/setup.bash && source ~/Swachh/Navigation/Simulation/vacuum_ws/install/setup.bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp CYCLONEDDS_URI=file://$HOME/Swachh/Navigation/cyclone_dds.xml ROS_LOCALHOST_ONLY=1
export ROS_DOMAIN_ID=0      # slot 0; slot 1 uses 11 (slot N>0 uses 10+N)
ros2 launch vacuum_bringup rviz.launch.py
```
Keep RViz closed during the Phase C test campaign (it slows runs and can make episodes invalid). Each episode saves `diagnose.png` for after-the-fact viewing.

## After the run
Tell the owner to: `sudo rm /etc/sudoers.d/hrishikesh`, `sudo deluser hrishikesh sudo`, unmask the sleep targets, and unshare the machine in Tailscale. Offer to tar the results (plan §11.5).

## Lessons from the 2026-10-25 run
- ROS apt repo: `packages.ros.org` serves a `*.osuosl.org` certificate (name mismatch); `/etc/apt/sources.list.d/ros2.list` uses **http** with `signed-by=/usr/share/keyrings/ros-archive-keyring.gpg` (fingerprint C1CF 6E31 E6BA DE88 68B1 72B4 F42E D6FB AB17 C654). `setup_machine.sh` aborts if `/opt/ros/jazzy` is missing: install `ros-jazzy-desktop ros-dev-tools` first.
- No DISPLAY over SSH and the desktop belongs to user `uzair`: always `VACUUM_GZ_HEADLESS_RENDERING=1` (`~/eval_setup/env.sh`). NVIDIA EGL works without the `render`/`video` groups (libEGL `/dev/dri` warnings are harmless). preflight's renderer line is empty without a display; check `nvidia-smi` for the gz process instead.
- **CPU, not GPU, is the limit:** 3 parallel SLAM sims gave load avg 67 on 16 threads and RTF ~0.74; use `--parallel 2` (RTF 1.0). GPU peaked at 66 C.
- **After any network change** (the PC moved Wi-Fi mid-run), stop the `ros2` daemon for domain 0 before launching; a stale daemon made G1_clock fail on slot 0.
- Effective depth camera HFOV is 69.4 deg (model uses the colour HFOV).
- Monitoring helpers in `~/eval_setup/`: `wait_timer.sh` (10-min capped watcher), `gpu_watch.sh` (thermal guard), `snapshot_results.sh` (light results copy + local commit), `results_table.py`.
