# What to put in paper.txt: the two empty subsections, and where each figure goes

**Written for:** the paper authors. All numbers below come from `docs/paper_out/paper_values.json` (script-generated, double-checked); copy the image files in `docs/paper_out/figures/` next to `paper.txt` (same way as `SBY ARCHI.png`).

## 1. Obstacle Avoidance Performance (paper.txt line 1133, currently empty)

Replace the commented sentence with:

```latex
\subsection{Obstacle Avoidance Performance}
\label{sec:avoid_results}

Obstacle avoidance was tested in two simulated scenarios, with three random seeds each (six episodes, all valid). In \texttt{avoid\_u\_trap} the robot must reach a goal past a static U-shaped trap. In \texttt{avoid\_dynamic\_sudden} a $0.4 \times 0.4$~m box starts moving at $0.5$~m/s from behind a wall while the robot drives to its goal. A trial counts as successful only if the robot reaches the goal without any contact with an obstacle.

The robot succeeded in 3 of 3 trials in the static scenario and in 1 of 3 trials in the dynamic scenario, so 4 of 6 trials overall (66.7\%, 95\% Wilson interval 30.0 to 90.3\%). The goal was reached in 5 of the 6 trials, and one contact event occurred in total. The minimum distance to an obstacle averaged 0.159~m; this is slightly optimistic, because the wheels protrude about 2~cm beyond the footprint used for the measurement. With only three trials per scenario the intervals are wide. The result shows that the static trap was handled, and that the robot did not reliably avoid the suddenly moving obstacle. The robot also made contact with obstacles during exploration and navigation (Section~\ref{sec:slam_results}).

\paragraph{Responsiveness.}
With the SLAM stack running and the explorer disabled, the wall-clock step-response time (from a velocity command until the robot reaches 50\% of the commanded velocity) was 166~ms on average (95th percentile 206~ms), and the stop response time was 260~ms (95th percentile 301~ms), from two episodes. Both are below 0.5~s. The delay mostly reflects the configured acceleration ramp plus about 45~ms of pipeline delay. The two runs without the SLAM stack are marked invalid by the validity rules, which require RTAB-Map updates, and are excluded.
```

## 2. End-to-End System Performance (line 1136): what you can and cannot fill

The existing table asks for a latency per module from camera to Arduino. **Most of it was never measured.** Do not invent values. What exists:

| Row in the table | Status | Value / source |
|---|---|---|
| Camera capture + decode | not measured | none in the repository |
| YOLOv11n inference | measured on the **Jetson**, not the RTX-A6000 | 17.10 ms with TensorRT FP16 (your Jetson Table in Section 6.3; the YOLOv8 INT8 value is 12.89 ms). Rename the row "YOLOv11 inference (Jetson Orin Nano, TensorRT FP16)" |
| SSD-MobileNet inference | no SSD-MobileNet in the project | delete the row |
| R-DETR inference | no Jetson measurement in the repository | leave as "not measured" or measure it |
| SLAM update (per frame) | not measured per frame; the run logs show roughly 0.05 to 0.2 s per RTAB-Map update on the **laptop CPU**, not the Jetson | measure on the Jetson, or delete the row |
| Decision module | not measured | none |
| Arduino command transmission | not measured | none |
| Velocity command to motion (simulation) | measured | 166 ms mean, 206 ms 95th percentile |
| Velocity command to stop (simulation) | measured | 260 ms mean, 301 ms 95th percentile |

**Recommendation:** either (a) measure the missing rows on the real robot (one timing script on the Jetson covers camera, decision and serial), or (b) replace the table by a short honest paragraph:

```latex
\subsection{End-to-End System Performance}
The full chain from camera frame to actuator command has not yet been measured on the physical robot. Individually measured components are the on-device detector latency (Section~\ref{sec:edge}), and, in simulation, the response of the robot to a velocity command: 166~ms to reach half of the commanded velocity and 260~ms to stop (Section~\ref{sec:avoid_results}). End-to-end latency measurements on the Jetson are part of future work.
```

(Use whichever label your Edge Deployment subsection has instead of `sec:edge`.) Also note the table's caption row "Total" cannot be filled until every row exists.

## 3. Figure placement in paper.txt

Use `\includegraphics[width=\linewidth]{<file>}` inside `figure` like your existing ones. Captions are in `docs/paper_out/FIGURE_CAPTIONS.md`.

| # | Figure file | Put it in | Exact spot | What it shows (description for the reader) |
|---|---|---|---|---|
| 1 | `fig_test_worlds.png` | SLAM Navigation Performance | after the first paragraph (line 1077, "All experiments were conducted in Gazebo...") | Floor plans of the six held-out test worlds. Dark = walls and obstacles, light blue = floor the robot can reach |
| 2 | `fig_actual_vs_explored.png` | same subsection | right after `\end{table}` of `tab:slam_results` (about line 1096) | Real floor plan (left) and the SLAM map each of three seeds produced (right), per world. The maze shows two nearly empty maps |
| 3 | `fig_coverage_vs_time.png` | same subsection | after the coverage paragraph (line 1083) | Explored share of the reachable area over time, one line per episode |
| 4 | `fig_ate_points.png` | same subsection | after the "Trajectory error and contact" paragraph (line 1100) | Trajectory error per exploration episode; hollow markers = odometry corrupted by contact |
| 5 | `fig_nav_success.png` | same subsection | after `\end{table}` of `tab:nav_results` (about line 1121) | Navigation success per world: Nav2-reported (light) versus ground-truth verified (dark), with intervals |
| 6 | `fig_navigation_trajectories.png` | same subsection, optional | after fig 5 | Paths of all 12 navigation runs over the floor plans |
| 7 | `fig_exploration_trajectories.png` | optional, or an appendix | after fig 2 | Paths of the 9 exploration runs (it overlaps with fig 2, so skip if space is short) |
| 8 | `fig_costmap_layers.png` | Path Planning | after the costmap paragraph (line 777) or the parameter table (line 805) | SLAM map, global costmap and local costmap: lethal, inscribed and inflation zones |
| 9 | `fig_slam_map_office.png` | Visual SLAM | after the "Occupancy grid" paragraph (line 684), optional | A partial office map from a live run (redundant with fig 2; skip if short of space) |

Not included here because they are screenshots you take yourself: robot close-up and camera view (`FIGURE_PLAN.md`, S1 to S3), which belong in Robot Physical and System Specifications (line 156) and Obstacle Detection.

## 4. Template for one figure

```latex
\begin{figure}[htbp]
\centering
\includegraphics[width=\linewidth]{fig_actual_vs_explored.png}
\caption{Actual floor plan (left) and the occupancy grid explored by the robot in each of three runs. Maps are placed using the starting pose only, so warped shapes show SLAM drift. In the maze the explorer sent no goal in two of three runs.}
\label{fig:actual_vs_explored}
\end{figure}
```

Refer to it in the text as `Fig.~\ref{fig:actual_vs_explored}`; with `[htbp]` LaTeX may move it, so always cite it in the paragraph.

## 5. Things I noticed while checking paper.txt

- The pooled **Area** cell is `--` in the SLAM table. That is fine; add a note "area is per world" or put 106.4 (the sum) if you prefer.
- The Avoidance and End-to-End sections are the only empty ones in Experimental Results. The Conclusion (line 1167) is still commented out.
- The End-to-End table names **RTX-A6000** and **SSD-MobileNet**, neither of which is in this project (see error 10 in the earlier error list).
