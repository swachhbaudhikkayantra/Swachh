# 11. Object Detection / Camera: the stereo-camera detection and distance stack

Scope: everything under `/home/hrishikesh/Swachh/Object Detection/Camera/` (note the space in `Object Detection`; always quote the path in a shell). Sub-folders: `vision/`, `network/` (with `rpi_setup/` and `gpu_setup/`), `streamlit_app/`, plus `vision/calib/` and `vision/models/`.

Rule used in this document: it describes only what the code and files do. Anything that appears only in the paper (`/home/hrishikesh/Swachh/paper.txt`) or only in a README/comment and is not backed by code is marked **DESIGNED, NOT IMPLEMENTED** or **DOC DISAGREES WITH CODE**.

---

## 1. High-level picture

```
 2x Logitech C270 (USB, 640x480, MJPG, 10 fps)          [camera.py]
        |  left + right BGR frames
        v
 YOLOv8s ONNX detector (COCO weights, 7 allowed classes) [detector.py]
        |  list of Detection (box, conf, class, centroid), best first
        v
 Stereo depth for the BEST detection only                [depth.py]
        |  rectify -> StereoSGBM disparity -> median in 11x11 patch around centroid
        |  -> Z = f*B/d ; X,Y by pinhole back-projection
        |  (fallback: Z from bbox height if stereo gives nothing)
        v
 Decision gate: same class in N consecutive frames AND conf >= min_conf_to_send   [main.py]
        v
 Arduino serial command  ARM:PICK:<cls>,<X>,<Y>,<Z>,<conf>      [serial_comm.py]
```

There are two ways to run this pipeline:

| Mode | Where the detector runs | Entry point |
|---|---|---|
| Standalone (all-in-one) | On the same board as the cameras, ONNX Runtime **CPU** | `vision/main.py` (via `vision/run.sh`) |
| Distributed | Cameras + Arduino on a Raspberry Pi 5; YOLO + depth on a GPU PC (ONNX Runtime CUDA) | `network/rpi_publisher.py` (Pi) and `network/gpu_worker.py` (GPU PC) |

A third, separate tool, `streamlit_app/app.py`, is a webcam demo for a **different, custom-trained model** (21 class names, section 9). It is not part of the pick pipeline.

What "decision" means here: the only decision logic in this folder is the stability + confidence gate that decides whether to send an `ARM:PICK` command to the Arduino. There is no navigation decision, no state machine, and no arm control code in this folder.

---

## 2. Folder map

| Path (under `Object Detection/Camera/`) | Purpose |
|---|---|
| `vision/config.yaml` | All tunables for camera, inference, depth, serial, display |
| `vision/main.py` | Standalone orchestrator (capture, detect, depth, serial, display) |
| `vision/camera.py` | `StereoCam`: two threaded V4L2 capture workers |
| `vision/detector.py` | `Detector`: YOLOv8 ONNX inference, NMS, class filter |
| `vision/depth.py` | `StereoDepth`: rectification, SGBM, X/Y/Z, bbox fallback |
| `vision/serial_comm.py` | `ArduinoSerial`: `ARM:PICK` / `ARM:NO_TARGET` over serial |
| `vision/calib.sh`, `vision/save_calib.py` | Stereo calibration (ROS 2) and conversion to `.npz` |
| `vision/calib/stereo_calib.npz`, `vision/calib/calibration_values.yaml` | Calibration data (binary and human-readable) |
| `vision/models/yolov8s.onnx`, `vision/models/yolov8s.pt` | COCO-pretrained YOLOv8s (name from the ONNX metadata is COCO's 80 classes) |
| `vision/run.sh`, `vision/setup.sh` | Launcher and one-time setup |
| `vision/test_cameras.py`, `vision/test_detector_rpi.py` | Smoke tests |
| `vision/README.md` | Short readme (partly out of date, see section 11) |
| `network/network_config.yaml` | Ports, JPEG quality, ZMQ options |
| `network/rpi_publisher.py`, `network/gpu_worker.py` | The two ends of the distributed pipeline |
| `network/benchmark.py`, `network/journal_benchmark.py` | Transport/latency benchmarks |
| `network/rpi_setup/` | `hotspot_setup.sh`, `hotspot_stop.sh`, `sync_calib.sh` |
| `network/gpu_setup/` | `setup_windows.ps1`, `check_cuda.py`, plus unrelated ROS 2 Windows setup files |
| `network/README.md`, `network/gpu_handover_context.md` | Network docs (they disagree on IPs, section 7.6) |
| `streamlit_app/app.py`, `new_yolov8_best.onnx`, `new_yolov8_best.pt` | Streamlit demo and its custom model |

---

## 3. Configuration: `vision/config.yaml`

The one config file is read by `main.py`, and also by `rpi_publisher.py` and `gpu_worker.py` (they load `vision/config.yaml` from a path relative to the script).

| Section | Key | Value | Meaning / used by |
|---|---|---|---|
| camera | `left_device` / `right_device` | 0 / 1 | `/dev/video0`, `/dev/video1` (comment: video2 is a metadata node) |
| camera | `width`, `height`, `fps` | 640, 480, 10 | requested capture mode |
| camera | `exposure`, `brightness`, `gain` | 151, 108, 34 | applied with `v4l2-ctl` (same values as `calib.sh`) |
| camera | `auto_exposure`, `auto_white_balance`, `power_line_frequency` | 1, 0, 1 | `auto_exposure=1` means manual; WB off; 50 Hz |
| inference | `onnx_path` | `models/yolov8s.onnx` | relative to `vision/` |
| inference | `input_size` | 640 | stored by `Detector` as `_frame_h`; preprocessing itself uses the constant `IMG_SIZE = 640` |
| inference | `use_color` | `false` | false: grayscale replicated to 3 channels; true: BGR to RGB |
| inference | `conf_threshold` | 0.50 | score must be strictly greater (`scores > conf_thr`) |
| inference | `iou_threshold` | 0.60 | NMS IoU |
| inference | `frame_skip` | 1 | run inference every N frames in `main.py` (1 = every frame) |
| inference | `allowed_class_ids` | `[39, 41, 65, 67, 73, 76, 79]` | COCO IDs kept |
| depth | `calib_file` | `calib/stereo_calib.npz` | |
| depth | `min_disparity`, `num_disparities`, `block_size` | 0, 64, 9 | StereoSGBM |
| depth | `p1_coeff`, `p2_coeff` | 8, 32 | `P1 = 8*9*9 = 648`, `P2 = 32*9*9 = 2592` |
| depth | `disp12_max_diff`, `uniqueness_ratio` | 1, 10 | StereoSGBM |
| depth | `speckle_window_size`, `speckle_range` | 100, 32 | StereoSGBM |
| depth | `fallback_ref_object_height_cm` | 12.0 | assumed object height for fallback |
| depth | `fallback_focal_px` | 600 | assumed focal length for fallback |
| serial | `port`, `baud`, `timeout` | `/dev/ttyACM0`, 115200, 0.5 s | Arduino link |
| serial | `min_conf_to_send` | 0.55 | gate for sending `ARM:PICK` |
| serial | `stable_frames` | 2 | consecutive frames with same class before sending |
| display | `window_name`, `show_fps`, `show_depth`, `show_serial_status`, `box_color`, `text_color` | see file | only `window_name`, `show_depth`, `box_color` are read by `main.py`; `show_fps`, `show_serial_status`, `text_color` are not read anywhere in the code I read |

### Class names (the COCO detector)

`detector.py` holds the 80 COCO names in `COCO_NAMES`. Only these IDs pass the filter:

| COCO ID | Class name sent in `ARM:PICK` |
|---|---|
| 39 | bottle |
| 41 | cup |
| 65 | remote |
| 67 | cell phone |
| 73 | book |
| 76 | scissors |
| 79 | toothbrush |

The comment block in `config.yaml` lists a few other IDs (25 umbrella, 56 chair, 77 teddy bear, 78 hair drier) as discussed but excluded; they are comments only.

---

## 4. Module-by-module (`vision/`)

### 4.1 `camera.py`

- `_apply_v4l2_settings(device_path, cfg)`: runs `v4l2-ctl -d <dev> --set-ctrl=<name>=<value>` for six controls (`auto_exposure`, `exposure_time_absolute`, `brightness`, `gain`, `white_balance_automatic`, `power_line_frequency`), each with a 2 s timeout. Failures are logged as warnings only; unsupported controls are skipped silently.
- `_CamThread(device_id, width, height, fps)`: opens `cv2.VideoCapture(id, CAP_V4L2)`, raises `RuntimeError` if it cannot open, sets buffer size 1, size, fps, and FOURCC `MJPG`. A daemon thread reads frames in a loop into a `queue.Queue(maxsize=1)`; before each `put` it drops the old frame, so the queue always holds the newest frame. `read(timeout=0.1)` pops a frame (so a frame can be consumed only once) and returns `None` if none arrives within 0.1 s. `release()` stops the thread and releases the device.
- `StereoCam(cfg, use_color)`:
  - Opens the left camera (failure raises), then tries the right camera in a `try`. **If the right camera fails, it logs a warning and runs in "single camera mode"**: `self._right` stays `None`, and `read()` returns the left frame as both left and right.
  - `read()`: gets one frame from each queue; returns `(None, None)` if either is missing. If `use_color` is false both are converted to grayscale, otherwise they are returned as BGR.
  - `read_gray()`: calls `read()` on the two queues again and always returns grayscale (used for depth). Because each `read` pops the queue, these frames are **later captures than the ones returned by `read()`**, not the same frames. If a new frame does not arrive within 0.1 s (at 10 fps a frame arrives about every 0.1 s), it returns `(None, None)`; `main.py` then skips stereo and uses the fallback depth.
  - Default `right_device` in code is 2, but `config.yaml` sets 1 and that is what is used.

### 4.2 `detector.py`

- `_ONNXEngine(model_path)`: `onnxruntime.InferenceSession` with `CPUExecutionProvider` only (comment: "Use CPU provider for RPi 5"). `infer(tensor)` returns the first output.
- `_letterbox(img, size=640)`: scales by `min(size/h, size/w)`, pads equally to 640x640 with gray value 114. Returns image, ratio and `(dw, dh)` (pad).
- `_preprocess(frame, use_color)`: if `use_color` is false: grayscale (converted from BGR if needed), stacked into 3 identical channels; if true: BGR to RGB. Then letterbox, divide by 255, transpose to NCHW float32, written into a module-level buffer `_pre_buf`.
- `_nms(pred, conf_thr, iou_thr, allowed_ids)`: removes the batch dim; transposes if the array looks like `(4+C, N)` (only when `ncols < nrows and ncols <= 6`, which does not trigger for the standard `(84, 8400)` output, see note below); score = max of class scores, class = argmax; keeps rows with `score > conf_thr` and class in allowed IDs; converts xywh to xyxy; runs `cv2.dnn.NMSBoxes(boxes, scores, conf_thr, iou_thr)`; returns an `(N, 6)` array `[x1, y1, x2, y2, conf, cls]`. Empty-input guards return an empty `(0, 6)` array.
  - Note (from reading the code): the standard YOLOv8 ONNX output has shape `(1, 84, 8400)`. After removing the batch dim it is `(84, 8400)`, with `ncols=8400 > nrows`, so the transpose condition `ncols < nrows and ncols <= 6` is false and it is not transposed. The code then treats rows as boxes with `pred[:, 4:]` as class scores, which would be wrong for that shape. I did not run the model to check what shape the shipped `yolov8s.onnx` actually outputs, so I cannot say whether this misbehaves in practice. The repo has other `Object Detection` code (outside this scope) that may handle it differently.
- `Detection` dataclass: `x1, y1, x2, y2, conf, cls_id, cls_name, cx, cy, bbox_h` (all ints except conf).
- `Detector(model_path, cfg)`: reads `use_color`, `conf_threshold` (0.50), `iou_threshold` (0.60), `allowed_class_ids`; builds the engine. `detect(frame)`:
  1. Returns `[]` with a warning if the frame is `None`, empty or has a zero dimension ("dropped JPEG over network" guard).
  2. Preprocess; returns `[]` if the ratio is not finite or zero.
  3. Infer, then `_nms`.
  4. Un-pad and un-scale each box to original-frame pixels, clip to `[0, w-1]` / `[0, h-1]`, centroid = integer midpoint, `bbox_h = y2 - y1`.
  5. Sort by confidence, highest first. **The first element is treated as "the target" everywhere downstream.**

### 4.3 `depth.py`: stereo and fallback logic

`StereoDepth(calib_path, cfg)`:

1. Builds a `cv2.StereoSGBM_create` with the config values, mode `STEREO_SGBM_MODE_SGBM_3WAY`, `P1 = p1_coeff*block^2`, `P2 = p2_coeff*block^2`.
2. Stores fallback parameters (`fallback_ref_object_height_cm`, `fallback_focal_px`).
3. If `calib_path` exists, calls `_load_calib`; otherwise logs a warning and stays `ready = False`.

`_load_calib(path)` (wrapped in try/except; any error is logged and `ready` stays `False`):
- Loads `K1, D1, K2, D2, R1, R2, P1, P2, img_size` from the `.npz`.
- Builds rectification maps with `cv2.initUndistortRectifyMap(K, D, R, P, img_size, CV_32FC1)` for left and right.
- `focal = P1[0,0]`; `baseline = abs(P2[0,3]) / focal`; `cx0 = P1[0,2]`; `cy0 = P1[1,2]`.
- Sets `ready = True`.

`compute(left_gray, right_gray, cx, cy)` returns `(X, Y, Z)` or `(None, None, None)`:
1. If not `ready`: `(None, None, None)`.
2. Remap both grayscale frames with the rectification maps.
3. `disp = sgbm.compute(left_rect, right_rect) / 16.0` (SGBM output is fixed point with 4 fractional bits). This is a **full-frame** disparity computation each call.
4. Take an 11x11 window (radius 5) around `(cx, cy)`, clamped to the image; keep pixels with disparity `> 0`.
5. If none are valid: `(None, None, None)`. Otherwise `d = median(valid)`; if `d <= 0`: `(None, None, None)`.
6. `Z = focal*baseline/d`; `X = (cx - cx0)*Z/focal`; `Y = (cy - cy0)*Z/focal`. Returned rounded to 1 decimal. Any exception returns `(None, None, None)`.
7. Note: `cx, cy` are the centroid in the **un-rectified** left image (from the detector) but they index the **rectified** disparity map; the code does not map the centroid through the rectification.

`fallback_depth(bbox_h_px)`: returns `None` if `bbox_h_px <= 0`, else `round(fallback_ref_object_height_cm * fallback_focal_px / bbox_h_px, 1)`, i.e. `12.0 * 600 / bbox_height`. It uses a fixed assumed height and the assumed focal 600 px, not the calibrated focal.

**When the fallback is used (as coded in `main.py` and `gpu_worker.py`):**

| Condition | Result |
|---|---|
| Calibration file missing or failed to load (`ready == False`) | stereo not attempted; X, Y stay `None`; Z from bbox fallback |
| `cam.read_gray()` returns `None` (no new frame within 0.1 s) | stereo skipped this frame; Z from fallback (in `main.py`) |
| `compute` returns `None` (no valid disparity in the 11x11 patch, median <= 0, or exception) | Z from fallback; X, Y `None` |
| Single-camera mode (right camera failed to open, left duplicated as right) | the code does not detect this; both images are identical, so disparity is expected to be zero/invalid and the case is expected to land in the row above (not verified by running it) |
| `--no-depth` flag on `gpu_worker.py` | `depth_est` is `None`: no X/Y/Z at all, not even fallback |

When stereo succeeds, X, Y, Z all come from stereo. When the fallback is used, only Z is set.

**Computed limits of the shipped calibration (arithmetic from the stored numbers, not from a test):** `f = 1611.156 px`, `B = 0.153367` (from `calibration_values.yaml`). With `num_disparities = 64` and `min_disparity = 0`, the largest measurable disparity is below 64 px, so the smallest measurable depth is about `1611.156 * 0.153367 / 64 = 3.86` in baseline units (metres, see the next point). Closer objects exceed the disparity range.

**Units:** `calib.sh` calibrates with `--square 0.034` (metres) and `save_calib.py` comments "usually metres from ROS", so `baseline` and therefore stereo `Z/X/Y` are in **metres**. But `main.py`/`rpi_publisher.py` print `Z=...cm`, `depth.py`'s docstring says "usually cm", and the fallback is in **cm**. Both are rounded to 1 decimal. So the stereo path and the fallback path report values in different units under the same label (DOC DISAGREES WITH CODE). `journal_benchmark.py` names the same fields `X_m, Y_m, Z_m`.

### 4.4 `serial_comm.py`

`ArduinoSerial(cfg)`: reads `port` (`/dev/ttyACM0`), `baud` (115200), `timeout` (0.5 s).

| Method | Behaviour |
|---|---|
| `connect()` | opens the serial port, waits 2 s for Arduino reset, clears the input buffer; returns True/False. If `pyserial` is missing or the port fails, logs a warning and returns False (pipeline continues display-only) |
| `_send(command)` | thread-safe (lock); clears input, writes `command + "\n"` (ASCII), then reads lines until one starts with `ACK:` or `ERR:` or the timeout expires; returns that line or `None` |
| `send_pick(cls_name, X, Y, Z, conf)` | sends `ARM:PICK:<cls>,<X>,<Y>,<Z>,<conf>`; each coordinate printed with 1 decimal, or `?` when `None`; conf with 2 decimals. Returns True only if the reply starts with `ACK:` |
| `send_no_target()` | sends `ARM:NO_TARGET`; **exists but is never called** by `main.py` or `rpi_publisher.py` (the code has a `pass` branch with a comment about not flooding) |
| `disconnect()` | closes the port |

Example line on the wire: `ARM:PICK:bottle,12.3,-4.5,152.0,0.81`. The Arduino firmware is not in this folder, so the Arduino side of `ACK:`/`ERR:` is not verified here. (The paper, section on communication, describes the Jetson-Arduino link as 115200 baud, 8N1, newline-terminated ASCII commands with an acknowledgement; that matches the link settings used here, but the paper does not mention the `ARM:PICK` message.)

### 4.5 `main.py` (standalone loop)

Run from the `vision/` folder (it loads `config.yaml` and relative model/calib paths from the current directory).

Startup order: load config; `StereoCam`; check the model file exists (else exit); `Detector`; `StereoDepth`; `ArduinoSerial.connect()` (failure means "display-only mode"); `StabilityTracker`.

Per loop iteration:
1. `left, right = cam.read()`. If `None`, sleep 50 ms and retry.
2. If `frame_count % frame_skip == 0`: `last_dets = detector.detect(left)`. (`left` is grayscale when `use_color` is false; the detector handles both.) With `frame_skip` > 1, the previous detections are reused on skipped frames.
3. Resets `X, Y, Z = None`. If there is a detection: take `best = last_dets[0]`; if `depth_est.ready`, call `cam.read_gray()` and `depth_est.compute(left_gray, right_gray, best.cx, best.cy)`; if `Z` is still `None`, `Z = depth_est.fallback_depth(best.bbox_h)`.
4. `stable = tracker.update(best class name or None)`. `StabilityTracker` keeps a deque of the last `stable_frames` (2) class names (including `None`); it returns True only when the deque is full, all entries equal the current class, and it is not `None`. (It compares class names only, not position.)
5. If there is a detection, `stable` is True and `conf >= 0.55`: `arduino.send_pick(...)`. This is sent **every inference frame** while the condition holds; there is no one-shot or rate limit other than the loop rate.
6. Display: draws boxes (best = red-orange, thicker; others green), centroid dot, label `class conf%` plus `Z=..cm` for the best target, and a HUD (FPS, latency, mode BW/COLOR, `Depth: calib/fallback`, serial status, last command).

Keys: `q` / ESC quit; `c` toggles BW/colour for the detector; `d` toggles the depth label; `s` force-sends the current best target (debug).

Note: the HUD label "Depth: calib/fallback" shows whether calibration loaded (`depth_est.ready`), not whether the current frame used stereo.

### 4.6 Calibration

`calib.sh` (needs ROS 2 Humble, `usb_cam`, `camera_calibration`, `v4l2-ctl`, optionally `gnome-terminal`; it sources `/opt/ros/humble/setup.bash`):
1. Kills stale `usb_cam`, `cameracalibrator`, `stereo_matcher` processes (`pkill -9 -f`) and removes FIFOs.
2. Auto-detects the first two `/dev/video*` nodes that list YUYV or MJPG formats as left and right.
3. Sets the same v4l2 controls as `config.yaml`.
4. Starts two `usb_cam_node_exe` nodes (640x480, `mjpeg2rgb`, 10 fps) in namespaces `/left_camera`, `/right_camera`; waits for the topics and checks frames flow.
5. Starts `cameracalibrator --approximate 0.1 --size 7x5 --square 0.034` (7x5 inner-corner board, 34 mm squares).
6. Prompts you to collect samples (the script text says aim for 30-40 steady samples), press CALIBRATE and SAVE, then ENTER.
7. Runs `save_calib.py` on `/tmp/calibrationdata.tar.gz`, then prints a quality report using the epipolar error ("epi") from the log: below 0.5 "EXCELLENT", below 1.4 "MODERATE", otherwise "POOR". It also warns if `cx0` is negative or looks 700-999 (cameras pointing away/towards each other).

`save_calib.py` (`--tarball`, default `/tmp/calibrationdata.tar.gz`; `--out`, default `calib/stereo_calib.npz`): extracts `left.yaml` and `right.yaml`, parses `camera_matrix`, `distortion_coefficients`, `rectification_matrix`, `projection_matrix`, writes `stereo_calib.npz` and a human-readable `calibration_values.yaml` (with derived focal, baseline, cx0, cy0).

Contents of the shipped `vision/calib/stereo_calib.npz` (read directly): keys `K1, D1, R1, P1, K2, D2, R2, P2, img_size`; `img_size = [640, 480]`.

Values from `vision/calib/calibration_values.yaml` (generated 2026-03-26 13:14:48):

| Quantity | Value |
|---|---|
| Image size | 640 x 480 |
| Rectified focal (P1 fx = fy) | 1611.1562 px |
| Baseline (`abs(P2[0,3]) / fx`) | 0.153367 |
| Rectified principal point (P1) cx0, cy0 | 681.9205, 284.1711 |
| Left K | fx 1068.23, fy 1082.98, cx 426.70, cy 332.20 |
| Right K | fx 996.15, fy 1014.90, cx 366.05, cy 294.80 |
| Left R1 | rotation of about 0.2 in off-diagonal terms (e.g. R1[0,2] = -0.2024) |

Observation: the rectified principal point `cx0 = 681.9` is larger than the image width (640), which the `calib.sh` warning text describes as "Out-of-bounds cx0 (>640)" (cameras pointing towards each other). The code does not check or refuse this calibration. Left and right intrinsics also differ noticeably. The recorded epipolar error is not stored in the files, so I cannot state it.

### 4.7 Scripts and tests

- `run.sh [--color]`: finds the first two `/dev/video*` that list YUYV/MJPG (note: it detects devices itself but does **not** pass them to Python; `main.py` uses `left_device`/`right_device` from `config.yaml`), applies v4l2 settings, exits if `models/yolov8s.onnx` is missing, prints a note if the calibration is missing, then runs `./venv/bin/python3 main.py $EXTRA_ARGS`. `main.py` does not parse any command-line arguments, so `--color` has no effect in the code I read.
- `setup.sh`: `pip install ultralytics pyyaml pyserial onnxruntime "numpy<2.0.0"`; if `models/yolov8s.onnx` is missing, downloads `yolov8s.pt` and exports ONNX (imgsz 640, opset 17, simplify, static shape); then checks that the model, config and calibration exist. It does **not** create a `venv` (but `run.sh` expects `./venv/bin/python3`) and does not build a TensorRT engine, despite its header comment.
- `test_cameras.py`: opens both cameras with the same v4l2 settings, shows grayscale side-by-side preview; `q`/ESC quits. (Reads `right_device` from config with default 2.)
- `test_detector_rpi.py`: loads `Detector` with a minimal config and runs one inference on a black frame, prints the number of detections. Run from `vision/`.

---

## 5. Decision logic summary

| Step | Rule (as coded) | Value |
|---|---|---|
| Candidate objects | class in `allowed_class_ids` and score > `conf_threshold` | 7 COCO classes; 0.50 |
| NMS | `cv2.dnn.NMSBoxes` | IoU 0.60 |
| Target | highest-confidence detection | `last_dets[0]` |
| Distance | stereo for the target only; else bbox fallback | section 4.3 |
| Stability | same class name in `stable_frames` consecutive inference frames | 2 |
| Send gate | stable and `conf >= min_conf_to_send` | 0.55 |
| Output | `ARM:PICK:<cls>,<X>,<Y>,<Z>,<conf>` | `?` for unavailable coordinates |

Not implemented in this folder: tracking across frames by position, choice of target by distance, reachability check, repeated-send suppression, `ARM:NO_TARGET` transmission, any check of Arduino state, any navigation hand-off.

---

## 6. What is implemented versus what the paper says

| Topic | Implemented in `Camera/` | In the paper (`/home/hrishikesh/Swachh/paper.txt`) |
|---|---|---|
| Stereo C270 pair with SGBM depth and calibration | Yes (this document) | The paper lists a Logitech C270 for trash detection and a RealSense D435i; I found no description of C270 stereo/SGBM in it |
| Detector used by the pick pipeline | COCO-pretrained YOLOv8s ONNX with 7 COCO classes | The paper describes YOLOv8n, YOLOv11n-seg and RF-DETR trained on a custom 8-class dataset (877 images), benchmarked on a Jetson Orin Nano. That custom model is not what `vision/` loads |
| Compute platform | Raspberry Pi 5 (CPU ONNX) and/or Windows GPU PC over ZMQ; `vision/README.md` and comments also mention Jetson/TensorRT | Jetson Orin Nano as the onboard "brain" |
| Raspberry Pi + GPU PC split over ZMQ | Yes (section 7) | Not described (the RPi 5 line in the paper source is commented out) |
| Serial link | 115200 baud via `pyserial`, `ARM:PICK` | Paper: 115200, 8N1, newline-terminated ASCII, ack from Arduino; `ARM:PICK` is not mentioned |
| TensorRT engine | **Not implemented**: no `.engine` file, no TensorRT code; only comments/README text | Paper cites TensorRT/FP16 benchmarking on Jetson (done by other code, outside this folder) |
| Decision module pre-empting navigation when trash is seen | **Not implemented here** | "Planned integration" in the paper |

---

## 7. Network layer (`network/`)

### 7.1 Roles and sockets

| Side | Script | Sockets | Direction |
|---|---|---|---|
| Raspberry Pi 5 (cameras, Arduino) | `rpi_publisher.py` | `PUB` **binds** `tcp://*:5555`; `PULL` **binds** `tcp://*:5556` | sends frames, receives results |
| GPU PC | `gpu_worker.py` | `SUB` **connects** to `tcp://<rpi_host>:5555`, subscribed to topic `frame`; `PUSH` **connects** to `tcp://<rpi_host>:5556` | receives frames, sends results |

The Pi is the server (binds), the GPU PC is the client (connects). Transport is `pyzmq` over TCP; no broker.

### 7.2 Frame protocol (Pi to GPU)

A ZMQ multipart message of exactly 4 parts, sent with `pub.send_multipart`:

| Part | Content |
|---|---|
| 0 | topic, bytes `b"frame"` |
| 1 | JSON (UTF-8): `{"frame_id": <int, starts at 0>, "timestamp": <time.time() at send>}` |
| 2 | left image, JPEG bytes (`cv2.imencode(".jpg", ..., quality)`), colour BGR |
| 3 | right image, JPEG bytes |

`rpi_publisher.py` opens the camera with `StereoCam(cam_cfg, use_color=True)` and encodes both images at `jpeg_quality` (75). `frame_skip` (network config, 1) sends every Nth captured frame. The `frame_id` counter only increments for frames actually sent.

The GPU worker rejects messages with fewer than 4 parts ("Malformed", counted as an error), parses part 1 as JSON, decodes parts 2 and 3 with `cv2.imdecode(..., IMREAD_COLOR)`, and skips the frame if either decode fails.

### 7.3 Result protocol (GPU to Pi)

`push.send_json(result, zmq.NOBLOCK)` (if the buffer is full the result is dropped and a warning is logged):

```json
{
  "frame_id": 123,
  "detections": [
    {"x1": 0, "y1": 0, "x2": 0, "y2": 0, "conf": 0.812,
     "cls_id": 39, "cls_name": "bottle", "X": null, "Y": null, "Z": null}
  ],
  "det_ms": 18.4
}
```

- Detections are sorted best first (from `Detector.detect`).
- On the GPU side, depth is computed **only for the first detection** (`i == 0`). Other detections keep `X/Y/Z = null`.
- With a depth estimator present: if it is `ready`, it runs stereo on grayscale versions of the decoded left/right frames (so left and right are the same pair here, unlike the local `read_gray()` case); if `Z` is still `None` it uses `fallback_depth(bbox_h)`. With `--no-depth` no depth is added.
- The GPU worker only sends JSON; **the Arduino is on the Pi**, so the Pi applies the same stability/confidence gate as `main.py` (its own `StabilityTracker` copy, same `stable_frames` and `min_conf_to_send` read from `vision/config.yaml`) and calls `send_pick` with `X/Y/Z` from the result.
- The Pi matches `frame_id` to its send time to show latency; stale entries older than 30 ids are dropped. It reads results with `recv_json(NOBLOCK)`: **at most one result per loop iteration**, and if none is available it keeps drawing the previous detections.

### 7.4 `network_config.yaml`

| Key | Value | Meaning |
|---|---|---|
| `rpi.host` | `10.0.0.1` | Pi address (static Ethernet), used by the GPU side to connect |
| `rpi.pub_port`, `rpi.pull_port` | 5555, 5556 | frames, results |
| `gpu.jpeg_quality` | 75 | JPEG quality |
| `gpu.frame_skip` | 1 | send every Nth frame |
| `gpu.send_both_cameras` | true | **not read by any script I read** (both frames are always sent) |
| `gpu.recv_timeout_ms` | 300 | `RCVTIMEO` on the Pi PULL socket (only matters for blocking receives; the publisher uses NOBLOCK) |
| `zmq.hwm` | 2 | high-water mark (send/receive) so old frames are dropped rather than queued |
| `zmq.linger_ms` | 0 | |
| `zmq.reconnect_ivl_ms` | 500 | used by the GPU SUB socket (`RECONNECT_IVL`) |
| `zmq.reconnect_ivl_max_ms` | 5000 | **not read** by the scripts I read |

The bandwidth numbers in the file's comments (about 30 KB per JPEG, about 5 Mbps at 10 fps) are estimates written in comments, not measurements.

### 7.5 `gpu_worker.py` details

- Imports `Detector`, `StereoDepth` from `../vision` (it inserts that folder in `sys.path`), so the GPU PC needs the whole `Camera/` tree, `vision/config.yaml`, the model and (for depth) the calibration.
- Chooses providers: if `CUDAExecutionProvider` is available uses `["CUDAExecutionProvider", "CPUExecutionProvider"]`, else CPU with a warning. It does this by **monkey-patching** `onnxruntime.InferenceSession.__init__` to override `providers`, so the unchanged `Detector` runs on the GPU.
- Depth calibration path: `vision/` + `depth.calib_file` from the config; model path: `--model` or `vision/` + `inference.onnx_path`.
- SUB socket `RCVTIMEO = 5000`: after 5 s without frames it logs a warning and continues.
- Logs stats every 30 frames (FPS, detection ms, average latency, detections, errors) and a session summary on exit. The latency printed is `time.time() - frame timestamp`, so it compares clocks of two machines (accurate only if their clocks are in sync).
- Arguments: `--rpi-host`, `--config`, `--model`, `--no-depth`. Its help text says the default host is 192.168.4.1, but the actual default is whatever `network_config.yaml` says (10.0.0.1).
- Runs the detector with the config's `use_color` (false), so the colour JPEG is converted to grayscale-tiled input, the same as the standalone mode.

### 7.6 Which network? The docs disagree

| Source | Link described |
|---|---|
| `network/README.md` | Pi as Wi-Fi hotspot `swachh-bot`, Pi `192.168.4.1`, GPU about `192.168.4.101` |
| `network/gpu_handover_context.md` and `network_config.yaml`, `check_cuda.py` | Direct Ethernet: Pi `10.0.0.1`, GPU PC `10.0.0.2` (subnet 255.255.255.0, gateway 10.0.0.1), plus NAT on the Pi so the PC gets internet through the Pi's Wi-Fi |

The code and config in the folder use `10.0.0.1`. The hotspot scripts exist but the handover doc says the project moved to direct Ethernet. The NAT/iptables setup is described in the handover doc only; there is no script for it in this folder.

### 7.7 Pi-side setup scripts (`network/rpi_setup/`)

- `hotspot_setup.sh` (root; options `--ssid`, `--password`): configures `hostapd` + `dnsmasq` on `wlan0`: SSID `swachh-bot`, password `swachh2024` (defaults in the script), static IP `192.168.4.1`, DHCP range `192.168.4.100-200`, `hw_mode=g`, channel 6, WPA2-PSK with TKIP, country code IN. Edits `/etc/dhcpcd.conf` and backs up `dnsmasq.conf`.
- `hotspot_stop.sh` (root): stops/disables `hostapd` and `dnsmasq`, removes the block it added to `/etc/dhcpcd.conf`, restores the latest `dnsmasq.conf.backup.*` if present, restarts `dhcpcd`.
- `sync_calib.sh <gpu_ip>`: pings the GPU PC, creates the destination folder over SSH, and `scp`s `stereo_calib.npz` to `Desktop/swachh-boudhik-yantra/Camera/vision/calib/` on the Windows PC (needs OpenSSH Server there; env `GPU_USER`, default current user). Observation: it derives `CALIB_FILE` as `$REPO_ROOT/Camera/vision/calib/stereo_calib.npz` where `REPO_ROOT` is two levels above `rpi_setup/` (that is the `Camera/` folder itself in this layout), so the path would resolve to `Camera/Camera/vision/...`; I did not run it, so check the path before using it.

### 7.8 GPU-side setup (`network/gpu_setup/`)

- `setup_windows.ps1` (run in Administrator PowerShell): checks Python >= 3.10 and pip; creates venv `.\swachh-gpu-env`; installs `pyzmq`, `onnxruntime-gpu`, `opencv-python`, `numpy`, `pyyaml`; checks that ONNX Runtime lists `CUDAExecutionProvider`; adds Windows Firewall rules for TCP 5555 and 5556 (in and out); writes `run_gpu_worker.bat` and `run_check_cuda.bat`. (`journal_benchmark.py` additionally uses `psutil`, which this script does not install.)
- `check_cuda.py`: prints Python version, `nvidia-smi` GPU name/VRAM/driver/compute capability, ONNX Runtime providers (CUDA check), presence of `pyzmq`, OpenCV, NumPy, and pings `10.0.0.1`. Run it with the venv active.
- `setup_ros2_windows.ps1`, `monitor_ros2.ps1`, `ros2_dependencies_checklist.md`: an unrelated ROS 2 Humble + Nav2 install helper/checklist for Windows (progress file `C:\dev\ros2_progress.json`). Not used by the camera pipeline.

### 7.9 Benchmarks

| Script | What it does |
|---|---|
| `benchmark.py --mode sender` | Acts as the Pi: binds PUB 5555, sends synthetic frames, reports TX rate |
| `benchmark.py --mode receiver [--rpi-host IP]` | Acts as the GPU: SUB connects, reports RX rate/latency, no detection |
| `benchmark.py --mode roundtrip [--duration S] [--fps F]` (default mode, 30 s, 10 fps) | Pi side: binds PUB/PULL, sends synthetic JPEG frames (same JPEG sent as left and right), reads results from a running `gpu_worker.py`, prints min/avg/max round trip and "Effective FPS", saves a report |
| `journal_benchmark.py [--duration 120] [--fps 10] [--rpi-host] [--config] [--out CSV] [--pattern gradient\|noise\|solid]` | Run on the GPU PC next to `gpu_worker.py`. It **binds** PUB/PULL itself, so `gpu_worker.py` must be started with `--rpi-host 127.0.0.1` and the real `rpi_publisher.py` must be stopped. Samples GPU (via `nvidia-smi`) and CPU/RAM (via `psutil`) and writes a per-frame CSV (round trip, JPEG sizes, throughput, `det_ms`, detection 0 fields, timeouts) plus a summary |

The README's target table (round trip under 100 ms, at least 8 FPS, about 5 Mbps) is a target written in the doc; no measured results are stored in this folder (I did not find any benchmark output file in the folder).

---

## 8. How to set up and run

### 8.1 Standalone on one board (Pi 5, Jetson, or any Linux box with two cameras)

```bash
cd "/home/hrishikesh/Swachh/Object Detection/Camera/vision"
python3 -m venv venv && ./venv/bin/pip install opencv-python pyyaml pyserial onnxruntime "numpy<2" # setup.sh uses plain pip, not the venv
sudo apt install v4l-utils              # v4l2-ctl is required by camera.py / run.sh
./setup.sh                              # only needed if models/yolov8s.onnx is missing
python3 test_cameras.py                 # check both cameras
python3 test_detector_rpi.py            # check the model loads
./calib.sh                              # only if recalibrating (needs ROS 2 Humble)
./run.sh                                # needs ./venv/bin/python3
```

Checks before running: `config.yaml` device IDs match your cameras; `/dev/ttyACM0` exists (or the pipeline runs display-only); a display is available (it opens an OpenCV window).

### 8.2 Distributed mode

1. Network: Pi `eth0` static `10.0.0.1`, GPU PC `10.0.0.2` (per the handover doc), or edit `rpi.host` in `network_config.yaml` for your network. (Alternative per README: `sudo bash network/rpi_setup/hotspot_setup.sh`.)
2. GPU PC (Windows, Administrator PowerShell): `cd ...\Camera\network\gpu_setup`, `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, `.\setup_windows.ps1`. Copy `vision/models/yolov8s.onnx` to `Camera\vision\models\` on the PC. Run `python check_cuda.py` inside the venv.
3. Optional depth: copy `vision/calib/stereo_calib.npz` to the same place on the PC (`sync_calib.sh` or manual copy). Without it use `--no-depth`; if you do not pass `--no-depth` and the file is missing, the worker still runs and uses the bbox fallback for Z.
4. Start the worker first (GPU PC): `cd Camera\network` then `python gpu_worker.py` (options: `--rpi-host`, `--no-depth`, `--model`).
5. On the Pi: `cd Camera/vision` then `python ../network/rpi_publisher.py` (add `--test` to skip the Arduino). The Pi script uses `vision/config.yaml` for cameras and serial, and `q`/ESC to quit. If the GPU worker is not connected yet the HUD shows "GPU: WAITING...". Note that because the Pi's camera and serial code is in `vision/`, `rpi_publisher.py` needs `pyserial`, `opencv`, `pyzmq`, `pyyaml` on the Pi (it does not import `onnxruntime` or the detector).
6. Benchmark (optional): see section 7.9.

---

## 9. Streamlit app (`streamlit_app/`)

Purpose: a browser-based webcam demo of a **custom-trained** YOLOv8s model. Independent of `vision/` (no stereo, no serial, no network).

Files: `app.py`, `new_yolov8_best.onnx` (about 44.8 MB), `new_yolov8_best.pt` (about 22.5 MB).

Run (per the docstring): `venv/bin/streamlit run app.py`. Needs `streamlit onnxruntime opencv-python-headless pillow numpy`. There is no requirements file in this folder.

What the code does:
- `load_model()` (cached with `st.cache_resource`): loads `new_yolov8_best.onnx` from the app's folder with `CPUExecutionProvider`; shows an error and stops if the file is missing.
- `get_class_names(session)`: reads the `names` entry of the ONNX metadata with `ast.literal_eval`; if that fails it falls back to `class_0 ... class_79`.
- `preprocess`: BGR to RGB, resize by `640 / max(h, w)` (integer truncation), centre in a 640x640 canvas filled with 114, scale to 0-1, NCHW.
- `postprocess`: takes `outputs[0][0].T` (assumes `(4+nc, 8400)` layout), class = argmax, keeps rows with score >= the slider value, converts to pixel boxes. **There is no non-maximum suppression in this app**, so overlapping boxes for the same object can all be drawn.
- `draw_detections` draws boxes with a 16-colour palette by class and counts per class.
- UI: sidebar with confidence slider (0.10 to 0.95, default 0.40, step 0.05), camera index (0 to 4, default 0), a "Start camera" toggle, a model-status line. Main area shows the annotated frame; the right column shows per-class counts and a legend of the first 20 class names. A "Stop camera" button ends the loop. The page loads a Google Fonts stylesheet in its CSS (an external request from the browser).

Class names stored in `new_yolov8_best.onnx` metadata (read directly from the file; 21 classes):

| ID | Name | ID | Name | ID | Name |
|---|---|---|---|---|---|
| 0 | bolts | 7 | metallic_clips | 14 | plastic_caps |
| 1 | cardboard_strips_box_flaps | 8 | metallic_tools | 15 | plastic_cups |
| 2 | fittings | 9 | nuts | 16 | plastic_wrappers |
| 3 | floor | 10 | obstacle | 17 | screws |
| 4 | glass | 11 | onemoreglass | 18 | wall |
| 5 | gloves | 12 | papers | 19 | washers |
| 6 | masks | 13 | plastic bags | 20 | wires |

Because the legend shows only the first 20 names (`class_names[:20]`), class 20 (`wires`) is not listed in the legend although it can be detected.

The metadata also records `nms: False` and `simplify: True`, `batch: 1`, `dynamic: False` for the export.

I did not run this app, so I did not verify the model's accuracy or that the 21 classes relate to the paper's "8 classes"; the paper says its dataset has 8 classes (with six waste categories plus floor and obstacle), which does not match these 21 names. Treat the relationship between this model and the paper's models as unverified.

---

## 10. Models in the folder

| File | Type | Classes | Used by |
|---|---|---|---|
| `vision/models/yolov8s.onnx`, `yolov8s.pt` | YOLOv8s, COCO (metadata names list `person`, `bicycle`, ...) | 80, 7 allowed | `vision/*`, `network/gpu_worker.py` |
| `streamlit_app/new_yolov8_best.onnx`, `.pt` | custom YOLOv8 export | 21 (section 9) | `streamlit_app/app.py` only |

---

## 11. Known mismatches and caveats (observed from the files)

1. `vision/README.md` says `detector.py` is "YOLOv8s TensorRT" and lists `models/yolov8s.engine`; the code uses ONNX Runtime CPU and no `.engine` exists. Its re-calibration note refers to `../mvp/calib.sh`, which is not in this folder (the script is `vision/calib.sh`).
2. `detector.py`'s module docstring and class docstring say TensorRT; the implementation is ONNX Runtime.
3. Depth units: stereo path in metres (baseline from metre-scale calibration), fallback in cm, label says "cm" (section 4.3).
4. Shipped calibration has `cx0 = 681.9 > 640` and a smallest measurable depth of about 3.86 units with `num_disparities = 64` (section 4.3/4.6).
5. `read_gray()` fetches new frames rather than reusing the detection frames (section 4.1), so stereo can be skipped or slightly time-shifted in `main.py`; in the distributed mode the stereo pair is the matched, decoded pair.
6. `run.sh --color` is passed to `main.py`, which does not parse arguments; `send_no_target()` is never called; `show_fps`, `show_serial_status`, `text_color`, `send_both_cameras`, `reconnect_ivl_max_ms` are not read by the code I read.
7. `network/README.md` (hotspot, 192.168.4.x) versus `network_config.yaml` and the handover doc (Ethernet, 10.0.0.x).
8. The `_nms` transpose heuristic (section 4.2) and the Streamlit `postprocess` assume specific ONNX output layouts; I did not run the shipped models to confirm which layout applies.
9. `hotspot_setup.sh` ships a default Wi-Fi password in plain text (`swachh2024`); change it if the hotspot mode is used.

---

One-line summary: `Camera/` is a COCO-YOLOv8s (7 classes) + calibrated-stereo-SGBM (bbox-height fallback) pick-target pipeline that sends `ARM:PICK:<cls>,<X>,<Y>,<Z>,<conf>` to an Arduino, runnable standalone (`vision/main.py`) or split over ZMQ ports 5555/5556 between a Raspberry Pi and a CUDA GPU PC, plus an unrelated Streamlit demo of a 21-class custom model, with TensorRT, the paper's custom-detector pipeline, and `ARM:NO_TARGET` handling designed or mentioned but not implemented here.
