# Machine setup and preflight

Works on the WSL2 laptop and on a native Ubuntu workstation (e.g. HP Z4 with RTX A6000).
ROS 2 Jazzy needs Ubuntu 24.04; on 26.04 the apt packages may not exist (setup warns).

- `setup_machine.sh [--dry-run] [--yes]`: idempotent installer (apt, sysctl DDS buffers, WSL boot hook,
  ~/.bashrc exports, rosdep, colcon build, vacuum_eval tests). Uses sudo and prompts. Paths auto-detected.
- `preflight.sh`: read-only checks (buffers, stray gz/ruby processes, disk, RAM, env, build, DDS config,
  suggested `--parallel`, GPU renderer). Exit 1 on any FAIL. Never kills anything.

## Fresh machine
```bash
cd <repo>/Navigation/Simulation/scripts
./setup_machine.sh --dry-run     # review
./setup_machine.sh               # install and build
# WSL only: run `wsl --shutdown` from Windows once so the boot hook applies
source ~/.bashrc
./preflight.sh                   # run before every batch
```
With an NVIDIA GPU, Gazebo renders natively; leave `render_gpu` false (WSL d3d12 only).
