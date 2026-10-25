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
