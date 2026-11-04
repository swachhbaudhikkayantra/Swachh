# 12. Detection Models and Benchmarks

Scope: everything in `Object Detection/` except the `Camera/` folder. This covers the app, the benchmark scripts, the transport protocol, the `Metrics/` result files and the `Model weights/` folder.

Rule used in this document: every number comes from a file in the repo. Where the files do not record something (for example which machine produced a CSV), this is stated.

---

## 1. The big picture

The project detects trash and floor hazards from camera images. Three detector families were trained and are stored in the repo:

| Detector | Type | Task head | Input size (from code/config) | Where |
|---|---|---|---|---|
| YOLOv8 (nano, `yolov8n.pt` base) | CNN, anchor-free | detection | 640x640 | `Model weights/Yolov8/` |
| YOLOv11 (nano segmentation, `yolo11n-seg.pt` base) | CNN, anchor-free | segmentation (box + 32 mask coefficients) | 576x576 | `Model weights/Yolov11/` |
| RF-DETR Medium | Transformer (DINOv2 small windowed backbone), end-to-end, no NMS | detection (`segmentation_head: false`) | 448x448 | `Model weights/Rfdetr/` |

Trade-off the folder is built to study: **accuracy versus latency**.
- The two YOLO models were benchmarked for speed on an NVIDIA Jetson Orin Nano (the code and docstrings say so) using FP32, FP16 and INT8 precision.
- RF-DETR has accuracy (training/validation) numbers only. It was **not** put through the latency benchmark: `cli_benchmark.py` and `benchmark.py` list only YOLOv8 and YOLOv11 in their model tables.
- The YOLO files contain **no accuracy metrics** (no mAP files for YOLOv8/YOLOv11 in this folder). So the repo has latency for YOLO and accuracy for RF-DETR, but no single table that compares all three on both axes.

### Trash classes

There are 8 object classes (from `app.py` `CLASSES`, ids 0-7):

`aluminium_foil`, `bottle`, `cement_dust`, `floor`, `obstacle`, `paper`, `wooden_dust`, `wrapper`

RF-DETR's `training_config.json` lists 9 names (`num_classes: 9`): the same 8 plus a leading `swachh-baudhika-yantra` (the project/robot name, apparently a dataset-level label from Roboflow-style export). `floor` and `obstacle` are not trash; they let the robot know where it can drive and what to avoid.

---

## 2. File-by-file guide

| File | Size | What it is |
|---|---|---|
| `app.py` | 19,148 B, 493 lines | Streamlit "YOLO Live Detection" UI. Loads a chosen model/precision with ONNX Runtime and draws boxes. |
| `benchmark.py` | 57,189 B, 1327 lines | Streamlit "Scientific Benchmark" UI (Scenario A direct, Scenario B wireless). Heavier statistics (bootstrap B=2000, Welch t, Mann-Whitney, Cohen's d, Grubbs). |
| `cli_benchmark.py` | 46,218 B, 989 lines | Headless terminal benchmark. This is the script that writes the `benchmark_results*.csv/json` files. |
| `trt_inference.py` | 11,625 B, 312 lines | Builds and runs TensorRT engines (FP16/INT8) from the FP32 ONNX, using `ctypes` and `libcudart` directly. |
| `frame_protocol.py` | 9,054 B, 231 lines | Shared wire format for RPi-to-Jetson frames, ping/pong RTT, and detections sent back. |
| `rpi_sender.py` | 14,960 B, 384 lines | Streamlit sender that runs on the Raspberry Pi: captures camera, JPEG-encodes, streams over TCP. |
| `stats_utils.py` | 9,819 B, 258 lines | Pure NumPy/`math` replacements for the few `scipy.stats` functions used (no SciPy needed on the Jetson). |
| `run.sh` | 1,880 B | Menu launcher for the four tools above. |
| `requirements.txt` | 213 B | streamlit, opencv-python, onnxruntime, numpy, scipy, psutil (onnxruntime-gpu left commented out). |
| `Metrics/` | see section 6 | Benchmark and training outputs. |
| `Model weights/` | see section 3 | Trained models in several formats. |

### 2.1 `app.py` (live detection)
- Model table points to `yolov8/best_{fp32,fp16,int8}.onnx` and `yolov11/...` (YOLOv11 INT8 path is `best_int8 (1).onnx`, a different name from the file in the repo, `best_int8.onnx`).
- Providers requested: `CUDAExecutionProvider` then `CPUExecutionProvider`.
- Preprocess: resize to model size, BGR to RGB, divide by 255, NCHW float32.
- Post-process: take the max class score per anchor, confidence threshold from the UI, boxes converted from centre/width/height to corners, scaled to the original frame, then per-class NMS with `cv2.dnn.NMSBoxes`, IoU threshold 0.45.
- Latency shown in the UI is only the `session.run` call, timed with `time.perf_counter()`.

### 2.2 `trt_inference.py` (TensorRT)
- `build_engine(onnx_path, precision, cache_dir, workspace_gb=2)` parses the **FP32 ONNX** and builds a serialized engine, cached as `<onnx stem>_<precision>.trt` (so `best_fp32.onnx` + `fp16` gives `best_fp32_fp16.trt`). If the cache file exists it is loaded; otherwise it builds (the code comment says first build can take 2-8 minutes).
- FP16: sets `BuilderFlag.FP16`.
- INT8: sets INT8 plus FP16 fallback plus `PREFER_PRECISION_CONSTRAINTS`, with a **random-data min/max calibrator** (10 batches of `np.random.rand`). The code comment states this is "valid for latency benchmarking". It means INT8 latency is measured, but INT8 *accuracy* is not meaningful from this build.
- `TRTSession` imitates an ONNX Runtime session (`get_inputs`, `get_outputs`, `get_providers`, `run`). `run` copies the input to the GPU, executes, copies back and synchronizes the stream, so the timed region includes host-to-device and device-to-host copies.
- Provider string reported: `TensorrtExecutionProvider (FP16)` or `(INT8)`.

### 2.3 `frame_protocol.py` and `rpi_sender.py`
- Frame packet header format `!IQIIII` = 28 bytes: JPEG length, sender timestamp (microseconds), frame number, width, height, plus one more uint32 (the code comment at the top lists five fields but the format string has six; `benchmark.py` names the last one `quality`).
- PING (12 bytes) / PONG (20 bytes) are used to estimate round-trip time; one-way time is estimated from RTT.
- Detections go back from Jetson to RPi: header `DETS` + frame number + count (12 bytes), then 24 bytes per detection (x1, y1, x2, y2, conf, class_id as float32, coordinates normalised 0-1).
- Defaults: port 9876, JPEG quality 75. The RPi sender UI offers camera index 0-2, resolutions 1280x720 / 640x480 / 1920x1080, max FPS 5-60 (default 30).

### 2.4 `stats_utils.py`
Implements `t_ppf` (Student-t quantile by bisection), `skew`, `kurtosis`, `ttest_ind` (Welch), `mannwhitneyu` (normal approximation, tie-corrected) and a function called `shapiro`. Important: the function named `shapiro` actually computes the **D'Agostino-Pearson K-squared** normality test, not the true Shapiro-Wilk test (its docstring says so). Anywhere a log or card says "Shapiro-Wilk" it is this substitute.

---

## 3. Model weights folder

Sizes are exact byte counts from the file system. Binary files were not opened.

### Yolov8 (`Model weights/Yolov8/`)

| File | Bytes | What it is |
|---|---|---|
| `yolov8n.pt` | 6,549,796 | Original pretrained YOLOv8-nano PyTorch checkpoint (base model, name implies the stock one) |
| `best.pt` | 6,234,403 | Fine-tuned PyTorch checkpoint (best epoch) |
| `best_fp32.onnx` | 12,270,784 | FP32 ONNX export (the source for TensorRT engines) |
| `best_fp16.onnx` | 6,173,020 | FP16 ONNX export |
| `best_int8.onnx` | 3,356,912 | INT8 ONNX export |
| `best_fp32_fp16.trt` | 8,935,476 | Cached TensorRT FP16 engine |
| `best_fp32_int8.trt` | 4,973,676 | Cached TensorRT INT8 engine |

### Yolov11 (`Model weights/Yolov11/`)

| File | Bytes | What it is |
|---|---|---|
| `yolo11n-seg.pt` | 6,182,636 | PyTorch checkpoint of the YOLO11-nano segmentation model |
| `best_fp32.onnx` | 11,600,148 | FP32 ONNX export |
| `best_fp16.onnx` | 5,860,456 | FP16 ONNX export |
| `best_int8.onnx` | 3,316,952 | INT8 ONNX export |
| `best_fp32_fp16.trt` | 9,343,772 | Cached TensorRT FP16 engine |

There is no INT8 `.trt` engine for YOLOv11 (see section 5.4). There is no fine-tuned `best.pt` for YOLOv11 in the repo; `yolo11n-seg.pt` is the only `.pt`, and the file name suggests it may be the stock checkpoint, but the repo does not say which. The tensor shapes in the benchmark JSON (`1x44x6804` output) show a 8-class segmentation model: 4 box + 8 class + 32 mask = 44.

### Rfdetr (`Model weights/Rfdetr/`)

| File | Bytes | What it is |
|---|---|---|
| `rfdetr_fp32.onnx` | 119,843,445 | FP32 ONNX |
| `rfdetr_fp16.onnx` | 60,320,471 | FP16 ONNX |
| `rfdetr_int8.onnx` | 32,111,137 | INT8 ONNX |
| `training_config.json` | 3,557 | Full training configuration (see below) |
| `hparams.yaml` | 3 | Empty (`{}`) |

RF-DETR is about 10x larger on disk than YOLOv8-nano in FP32 (119.8 MB vs 12.3 MB).

RF-DETR training configuration (`training_config.json`): model `RFDETRMedium`, encoder `dinov2_windowed_small`, resolution 448, 300 queries, 4 decoder layers, hidden dim 256, 100 epochs, batch size 16, lr 1.0026e-4, encoder lr 1.5e-4, EMA decay 0.993, 9 classes, pretrained from `rf-detr-medium.pth`, CUDA device, AMP on, no early stopping. Paths in the config are Windows paths (`C:\Users\BMSCECSE\...`), so training ran on a Windows PC; the GPU model is not recorded.

---

## 4. How the benchmark measures latency (`cli_benchmark.py`)

### 4.1 Model matrix (the `MODELS` list)

| Model | Quant | Resolution | Backend | Source file |
|---|---|---|---|---|
| YOLOv8 | FP32 | 640x640 | `ort` (ONNX Runtime, CPUExecutionProvider) | `best_fp32.onnx` |
| YOLOv8 | FP16 | 640x640 | `trt` (TensorRT) | engine built from `best_fp32.onnx` |
| YOLOv8 | INT8 | 640x640 | `trt` | engine built from `best_fp32.onnx` |
| YOLOv11 | FP32 | 576x576 | `ort` CPU | `best_fp32.onnx` |
| YOLOv11 | FP16 | 576x576 | `trt` | engine from FP32 ONNX |
| YOLOv11 | INT8 | 576x576 | `trt` | **skipped** (`skip: True`) |

Key point: **FP32 runs on the CPU** (ONNX Runtime CPU provider) while **FP16 and INT8 run on the GPU through TensorRT**. So the FP32-to-FP16 gap in the results mixes two effects: precision and device (CPU vs GPU). It is not a pure precision comparison.

The skip reason written in the code: "TRT 10.3.0: no INT8 kernel for YOLOv11-seg prototype head (model.23/proto)". Hence the YOLOv11 INT8 row is absent from all CSVs.

### 4.2 Protocol

Defaults (`argparse`): `--frames 150`, `--runs 3`, `--warmup 10`, `--interval 1000` (tegrastats interval in ms), `--images` (folder, optional), `--wireless`, `--port 9876`. `run.sh` option 4 runs `python3 cli_benchmark.py --frames 150 --runs 3 --warmup 10 --interval 1000`.

For each model:
1. **Load/build session** and time it (`load_time_ms`). For TensorRT the first build is included if no cached `.trt` exists; with a cached engine it is just deserialization.
2. **Warm-up**: 10 frames are run and discarded (lets GPU clocks, caches and lazy initialisation settle).
3. **First-frame latency**: one more timed inference (`First_Frame_ms` is the total pipeline for that frame: network + decode + preprocess + inference; in direct mode that is mostly inference).
4. **Measurement**: 3 trials x 150 frames = 450 timed inferences per model (confirmed by `n_frames_total: 450` in the JSON). There is a 1 second sleep between trials as a thermal cool-down.
5. **Per-frame timing**: `time.perf_counter()` immediately before and after `sess.run(...)` only. Image preprocessing and NMS/decoding are **not** inside the inference time.
6. **Input frames (Scenario A)**: a fixed random 1280x720 image (`numpy` seed 42), pre-preprocessed once and reused, unless `--images` gives real pictures. Because the frame is random noise, it produces no meaningful detections; this is fine for timing but means the benchmark says nothing about accuracy.
7. **Hardware sampling**: a background `tegrastats` process (`/usr/bin/tegrastats --interval 1000`) is parsed for GPU load (`GR3D_FREQ`), RAM, per-core CPU, temperatures (cpu, gpu, tj) and power rails (`VDD_IN` = total, `VDD_CPU_GPU_CV`, `VDD_SOC`). At a 1000 ms interval and runs of a few seconds, each model gets only a handful of samples, so the GPU/CPU/power columns are coarse.

### 4.3 Scenarios
- **Scenario A "Direct"**: frames come from memory; no network. Output files `benchmark_results.csv/json` (these were identical to `benchmark_results_scenario_a.*`; the CSVs are byte-identical, same size 1,634 B for both).
- **Scenario B "Wireless"**: `--wireless` starts a TCP server (`WirelessReceiver`); the Raspberry Pi sends JPEG frames; the Jetson measures a baseline RTT first (20 pings), then for each frame records network transit, JPEG decode time, preprocess time and inference, and sends detections back. The network-transit figure is the *constant* one-way estimate derived from the RTT, not a per-packet measurement (that is why `Net_Transit_ms` is 6.55 for every row).

### 4.4 Statistics computed over the 450 samples
(`calc_dist_metrics`, using `stats_utils`)

- Mean, SD with `ddof=1`, SEM = SD / sqrt(n).
- **95% confidence interval** = mean +/- t(0.975, n-1) x SEM (Student's t).
- Median, Q1, Q3, IQR; P90, P95, P99; min, max.
- CV% = SD / mean x 100.
- Avg FPS = 1000 / mean latency (model inference only).
- Also computed and stored in the JSON: SEM, bootstrap 95% CI (1000 resamples, seed 42), skewness, excess kurtosis, a normality p-value (on the first 1000 samples), per-trial means and the SD of trial means. In every JSON entry the normality p-value is 0.0 (latency distributions are not normal).
- **Deadline miss rate (DMR)**: share of frames whose *end-to-end* time exceeds 33.33, 50, 100 or 200 ms. (The console text writes it as "DMR(<33ms)", but the code counts frames above the threshold.) Only filled in Scenario B; "N/A" in Scenario A.
- **Energy**: average total power (W) from `VDD_IN`, then `FPS_per_Watt = FPS / W` and `mJ_per_Infer = W x mean latency (ms)`.

### 4.5 What the Streamlit `benchmark.py` adds
It documents the intended methodology: 100 ms tegrastats polling, bootstrap with B=2000, Grubbs/Tukey outlier counts, Welch t-test, Mann-Whitney U and Cohen's d for model-vs-model comparison. These comparison tests are in the code; no output file in `Metrics/` contains them.

---

## 5. Metrics folder: files and CSV columns

### 5.1 File list

| File | Size | Content |
|---|---|---|
| `benchmark_results.csv` / `.json` | 1,634 B / 17,390 B | Scenario A (direct) results. JSON timestamp `2026-09-23T20:44:52`. |
| `benchmark_results_scenario_a.csv` / `.json` | 1,634 B / 17,390 B | Identical in size to the above (CSVs are identical). |
| `benchmark_results_scenario_b.csv` / `.json` | 1,673 B / 35,103 B | Scenario B (wireless). JSON timestamp `2026-09-23T20:32:29`. |
| `benchmark_20260604_170435.csv` + `.summary.json` | 40,754 B + 1,073 B | Network test run 1 (failed, see 5.3). |
| `benchmark_20260604_170808.csv` + `.summary.json` | 142,337 B + 1,155 B | Network test run 2 (worked, see 5.3). |
| `rfdetr_metrics.csv` | 121,304 B | RF-DETR training log, 506 rows. |

**Hardware recording:** the CSV/JSON benchmark files contain no hardware field (the JSON has only `timestamp` and `results`). The statement that they were measured on a Jetson Orin Nano comes from the script title, docstring and the use of `tegrastats`/TensorRT, not from the result files. The exact Jetson power mode and JetPack version are not recorded (the code comment mentions TensorRT 10.3.0). The June network-test summaries record `platform: DESKTOP-SU3OTED` (a Windows machine name) and CSV paths on `C:\Users\BMSCECSE\Desktop\swachh-boudhik-yantra\Camera\network\`. The RF-DETR training config also points at `C:\Users\BMSCECSE\...`.

### 5.2 Columns of `benchmark_results*.csv` (37 columns)

| Column | Meaning |
|---|---|
| `Model`, `Quantization` | YOLOv8/YOLOv11 and FP32/FP16/INT8. |
| `Input_Resolution` | Model input size (640x640 or 576x576). |
| `Size_KB` | File size in KB of the FP32 ONNX used. For TensorRT rows it is still the **FP32 ONNX size** (YOLOv8 12,270,784 B / 1024 = 11,983.2 KB, YOLOv11 11,328.3 KB), so it does not show the smaller FP16/INT8 size. |
| `Provider` | `CPUExecutionProvider`, or `TensorrtExecutionProvider (FP16)` / `(INT8)`. |
| `Mean_Latency_ms`, `SD_ms` | Mean and sample SD of per-frame inference time. |
| `CI_95_Lo_ms`, `CI_95_Hi_ms` | Student-t 95% CI of the mean. |
| `Median_ms`, `IQR_ms` | Median and interquartile range. |
| `P90_ms`, `P95_ms`, `P99_ms` | Tail percentiles. |
| `Min_ms`, `Max_ms` | Extremes. |
| `CV_Percent` | SD / mean x 100 (stability). |
| `Avg_FPS` | 1000 / mean latency. |
| `First_Frame_ms` | Total pipeline time of the first measured frame (after warm-up). |
| `Cold_Start_TTFF_ms` | Time to first frame: session load/build time + first-frame pipeline time. |
| `E2E_Mean_ms` | Mean of network + JPEG decode + preprocess + inference (Scenario B only). |
| `Net_Transit_ms`, `JPEG_Decomp_ms`, `Preproc_ms` | Mean stage times (Scenario B only). |
| `DMR_33ms_pct` ... `DMR_200ms_pct` | Percent of frames with E2E time over 33.33 / 50 / 100 / 200 ms (Scenario B only). |
| `Goodput_Mbps` | Received payload bits per second over the benchmark duration (Scenario B only). |
| `GPU_Avg_Pct`, `GPU_Peak_Pct` | tegrastats GPU load average / peak. |
| `CPU_Avg_Pct` | Average of per-core CPU load. |
| `Temp_GPU_C`, `Temp_Tj_C` | Average GPU and junction temperature. |
| `Power_Total_W` | Average total board power (`VDD_IN`). |
| `FPS_per_Watt`, `mJ_per_Infer` | Efficiency measures defined in 4.4. |

Scenario A has "N/A" in all network/E2E/DMR/goodput columns.

### 5.3 Network test files (June 2026)

Per-frame CSV columns (28): `frame_id`, `wall_clock_utc`, `network_one_way_ms`, `round_trip_ms`, `frame_size_left_bytes`, `frame_size_right_bytes`, `total_payload_bytes`, `throughput_mbps`, `det_ms`, `num_detections`, `det0_class`, `det0_confidence`, `det0_x1`, `det0_y1`, `det0_x2`, `det0_y2`, `det0_cx`, `det0_cy`, `det0_X_m`, `det0_Y_m`, `det0_Z_m`, `gpu_util_pct`, `gpu_mem_used_mb`, `gpu_temp_c`, `cpu_util_pct`, `ram_used_mb`, `result_timeout`, `jpeg_quality`. The two `frame_size` columns suggest a stereo (left/right) camera pair; `det0_X/Y/Z_m` are 3D position fields of the first detection.

| | Run 1 (17:04:35) | Run 2 (17:08:08) |
|---|---|---|
| Target FPS / JPEG quality | 10 / 75 | 10 / 75 |
| Duration | 120.1 s | 120.03 s |
| Frames sent / received | 382 / 0 | 1157 / 1157 |
| Timeouts | 382 | 0 |
| Packet delivery ratio | 0.0% | 100.0% |
| Effective FPS | 0.0 | 9.6389 |
| Round-trip mean / SD / p95 / p99 (ms) | N/A | 50.978 / 4.637 / 56.964 / 61.085 |
| Inference (`det_ms`) mean / SD / p95 / p99 (ms) | N/A | 50.587 / 3.685 / 54.200 / 58.352 |
| Bandwidth mean (Mbps) | N/A | 2.150 |

Run 1 got no replies at all (every frame timed out). In run 2 every row has `num_detections = 0` (no detection ever returned), and inference was 39.6-89.2 ms. The summary does not name which detector was serving, and `one_way_latency_ms` equals `round_trip_ms` in this file (the CSV's `network_one_way_ms` and `round_trip_ms` are identical). So treat these as a pipeline/network test, not a model benchmark. The platform is recorded as `DESKTOP-SU3OTED`; the server hardware that produced `det_ms` is not stated.

### 5.4 `rfdetr_metrics.csv` (training log)

506 rows, epochs 0-99, one `step` every 50 steps for training rows (100 training-loss rows) and 100 validation rows (one per epoch). Column groups:
- `train/loss`, `train/loss_ce`, `train/loss_bbox`, `train/loss_giou` plus `_0/_1/_2/_enc` variants for auxiliary decoder layers and the encoder, `train/class_error`, `train/cardinality_error*`, `train/lr`, `lr_max`, `lr_min`.
- `val/mAP_50`, `val/mAP_50_95`, `val/mAP_75`, `val/precision`, `val/recall`, `val/F1`, `val/mAR`, `val/loss`, EMA versions `val/ema_mAP_50`, `val/ema_mAP_50_95`, `val/ema_mAR`.
- `val/AP/<class>` per-class average precision for the 8 trash classes.

Key RF-DETR validation numbers (rows with validation values):

| Point | Epoch | mAP@50 | mAP@50-95 | mAP@75 | Precision | Recall | F1 |
|---|---|---|---|---|---|---|---|
| First | 0 | 0.9037 | 0.8086 | 0.8504 | 0.8784 | 0.8502 | 0.8618 |
| Best mAP@50-95 | 12 | 0.9255 | 0.8387 | 0.8795 | 0.9354 | 0.8979 | 0.9151 |
| Best mAP@50 | 16 | 0.9336 | 0.8365 | 0.8721 | 0.9470 | 0.8926 | 0.9173 |
| Last | 99 | 0.9195 | 0.8160 | 0.8458 | 0.9271 | 0.8935 | 0.9092 |

The last-epoch EMA values are mAP@50 0.9208 and mAP@50-95 0.8191. Training loss went from 6.2426 (first logged row) to 3.1862 (last). Validation peaked early (epochs 12-16) and ended slightly lower, so the last epoch is not the best one; the repo does not say which epoch the exported ONNX files use.

Per-class AP at epoch 99 (best-epoch per-class values not extracted): aluminium_foil 0.961, floor 0.895, wrapper 0.865, bottle 0.844, paper 0.808, wooden_dust 0.754, obstacle 0.743, cement_dust 0.656. The dust classes and obstacle are the weakest.

The validation set, the IoU/area conventions and whether these mAP values are COCO-style are not stated in the folder.

---

## 6. Key latency numbers (from the CSVs)

All latencies are model-inference milliseconds, 450 frames per row, on the Jetson Orin Nano as indicated by the script (hardware not recorded in the file).

### 6.1 Scenario A (direct), `benchmark_results.csv`

| Model | Quant | Provider | Mean (ms) | SD | 95% CI (ms) | Median | P95 | P99 | FPS | Power (W) | mJ/infer |
|---|---|---|---|---|---|---|---|---|---|---|---|
| YOLOv8 | FP32 | CPU | 187.557 | 45.470 | 183.852-191.261 | 175.708 | 269.374 | 344.551 | 5.33 | 10.508 | 1970.907 |
| YOLOv8 | FP16 | TensorRT | 15.029 | 2.812 | 14.800-15.258 | 14.705 | 18.244 | 25.392 | 66.54 | 9.175 | 137.895 |
| YOLOv8 | INT8 | TensorRT | 12.888 | 2.753 | 12.663-13.112 | 13.060 | 17.379 | 19.515 | 77.59 | 8.296 | 106.919 |
| YOLOv11 | FP32 | CPU | 186.376 | 38.230 | 183.262-189.491 | 173.765 | 262.382 | 310.037 | 5.37 | 10.599 | 1975.465 |
| YOLOv11 | FP16 | TensorRT | 17.095 | 2.679 | 16.877-17.314 | 16.794 | 23.352 | 24.517 | 58.50 | 9.200 | 157.277 |

Other columns: first-frame / cold-start: YOLOv8 FP32 194.00 / 250.99 ms, FP16 17.05 / 260.97, INT8 17.00 / 72.73; YOLOv11 FP32 298.33 / 387.61, FP16 12.55 / 147.68. GPU average 49.7-65.8%, GPU temperature 60.1-62.6 C, Tj 61.6-63.9 C. Min-max: YOLOv8 FP16 8.579-33.529 ms, YOLOv8 INT8 7.165-20.177 ms.

### 6.2 Scenario B (wireless), `benchmark_results_scenario_b.csv`

| Model | Quant | Mean (ms) | SD | P95 | P99 | FPS | E2E mean (ms) | Net (ms) | JPEG decode (ms) | Preproc (ms) | DMR 33 / 50 / 100 / 200 (%) | Goodput (Mbps) | Power (W) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| YOLOv8 | FP32 | 122.699 | 28.168 | 175.030 | 195.101 | 8.15 | 138.70 | 6.55 | 5.25 | 4.19 | 100.0 / 100.0 / 100.0 / 2.4 | 4.52 | 9.766 |
| YOLOv8 | FP16 | 14.996 | 1.289 | 15.386 | 15.599 | 66.69 | 33.14 | 6.55 | 8.07 | 3.52 | 41.3 / 0.2 / 0.0 / 0.0 | 5.15 | 6.560 |
| YOLOv8 | INT8 | 12.444 | 0.619 | 12.861 | 13.948 | 80.36 | 31.51 | 6.55 | 8.76 | 3.75 | 47.1 / 0.0 / 0.0 / 0.0 | 5.13 | 6.422 |
| YOLOv11 | FP32 | 129.502 | 30.891 | 183.103 | 246.710 | 7.72 | 144.30 | 6.55 | 5.21 | 3.03 | 100.0 / 100.0 / 100.0 / 4.7 | 4.31 | 9.851 |
| YOLOv11 | FP16 | 20.047 | 5.781 | 32.285 | 47.326 | 49.88 | 37.66 | 6.55 | 7.88 | 3.18 | 68.0 / 4.9 / 0.0 / 0.0 | 4.79 | 7.050 |

Notes: CPU FP32 was faster in Scenario B (122.7 ms) than in Scenario A (187.6 ms) for YOLOv8; the files do not explain this, and since the JSON shows trial means of 121-123 ms in B and 180-201 ms in A, it is consistent across trials. A plausible cause (not proven by the files) is different CPU load or clock state between the two sessions. Scenario B's GPU average in the CSV is 24.6% for FP16/INT8 versus 65.8%/63.5% in A; these come from coarse tegrastats samples.

### 6.3 Reading the results

- **GPU TensorRT is about 12-15x faster than the CPU FP32 path** (YOLOv8: 187.6 ms to 15.0 ms FP16, 12.9 ms INT8). The comparison includes the device change, so it is not a pure precision effect.
- **INT8 is about 14% faster than FP16 for YOLOv8** (12.888 vs 15.029 ms in A; 12.444 vs 14.996 in B) and had lower SD.
- **YOLOv8 beats YOLOv11-seg on latency** at FP16 (15.0 vs 17.1 ms in A, 15.0 vs 20.0 ms in B). YOLOv11 is segmentation with an extra mask head; YOLOv8 is detection only, so this is not a like-for-like architecture comparison. YOLOv11 also runs at the smaller 576 input.
- **Real-time budget:** all GPU rows stay far under 33.33 ms of inference. In Scenario B the end-to-end time (31.5-37.7 ms) is close to the 33 ms budget because JPEG decoding (7.9-8.8 ms), preprocessing (3.0-3.8 ms) and the fixed 6.55 ms network estimate add about 18-19 ms to inference. DMR at 33 ms is 41.3-68.0% for GPU models, nearly 0% at 50 ms.
- **Energy:** FP16/INT8 TensorRT use roughly 14-19x less energy per inference than CPU FP32 in Scenario A (e.g. YOLOv8 106.9 mJ INT8 vs 1970.9 mJ FP32).
- **Accuracy side:** only RF-DETR validation scores exist (best mAP@50-95 0.8387 at epoch 12). Without YOLO accuracy numbers or an RF-DETR latency, the repo cannot answer "which detector is best overall"; the YOLO INT8 models were built with random calibration data, so their accuracy is unverified.

### 6.4 Caveats to keep in mind
1. Synthetic noise input in Scenario A: timing only; no detection output is meaningful.
2. `Size_KB` always shows FP32 ONNX size.
3. The "Shapiro-Wilk" test in logs is D'Agostino-Pearson.
4. DMR uses end-to-end time; in Scenario A the `Preproc_ms` is just the iterator fetch time (frames were preprocessed beforehand).
5. `app.py`/`benchmark.py` reference `best_int8 (1).onnx` for YOLOv11, which does not exist under that name in the repo; the file is `best_int8.onnx`.
6. Code paths use lowercase folders (`yolov8/`, `yolov11/`) placed next to the script, while the repo has `Model weights/Yolov8/` and `Yolov11/`. To run, copy or link the weights into those lowercase folders next to the scripts.
7. Hardware, power mode, JetPack and clocks are not stored in the result files.

---

## 7. How to rerun

On the Jetson Orin Nano (needs `tegrastats`, TensorRT, CUDA, `onnxruntime`, OpenCV, NumPy):

```bash
cd "Object Detection"
# put weights where the code expects them
mkdir -p yolov8 yolov11
cp "Model weights/Yolov8/best_fp32.onnx"  yolov8/
cp "Model weights/Yolov11/best_fp32.onnx" yolov11/
# optionally also copy the cached .trt engines next to them to skip the build

pip install -r requirements.txt
python3 cli_benchmark.py --frames 150 --runs 3 --warmup 10 --interval 1000   # Scenario A
```

Optional:
- Real pictures instead of noise: add `--images /path/to/images/`.
- Scenario B: start `python3 cli_benchmark.py --wireless --port 9876` on the Jetson, then on the Raspberry Pi run `streamlit run rpi_sender.py`, enter the Jetson IP and click "Connect & Stream".
- Menu launcher: `./run.sh` (1 live UI, 2 Streamlit benchmark, 3 RPi sender, 4 CLI benchmark, default 4).
- Output is written to `benchmark_results.csv` and `.json` in the script folder (it overwrites the previous run; rename the files afterwards to keep Scenario A and B separate, as was evidently done for `_scenario_a` and `_scenario_b`).
- The first TensorRT FP16/INT8 run builds engines (minutes). INT8 uses random calibration, and YOLOv11 INT8 is skipped by design.
- RF-DETR has no benchmark entry in the scripts; to measure it, a new `MODELS` entry and a transformer-style decoder (no NMS, different output tensors) would be needed.

---

**One-line summary:** The folder holds YOLOv8, YOLOv11-seg and RF-DETR weights in several precisions, a Jetson benchmark that shows TensorRT FP16/INT8 at about 12-20 ms per frame versus about 187 ms for CPU FP32 on the two YOLO models, and RF-DETR validation scores (best mAP@50-95 0.839); there is no single dataset that compares all three on both accuracy and latency, and the result files do not record the hardware.
