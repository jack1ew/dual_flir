# dual_flir

Resources and experiments for combining dual FLIR sensors with YOLO-based face detection. The repository currently carries curated documentation, pretrained weights, and the upstream YOLO Face package to support local prototyping.

## Repository layout
- `classes/` – place to record class label definitions or dataset-specific metadata for FLIR experiments.
- `script/` – custom helper scripts (add your own utilities here).
- `yolo/yolo-face/` – vendor drop of the [Ultralytics YOLO Face](https://github.com/derronqi/yolo-face) project, including multiple pretrained models (`.pt`, `.onnx`, `.engine`) and its full source tree.
- `*.pdf` – hardware integration notes and vendor documentation referenced during development.

## Getting started
1. Use Python 3.10+ and create a virtual environment for isolation.
2. Install dependencies for the YOLO Face package:
   ```bash
   pip install -r yolo/yolo-face/requirements.txt
   ```
3. (Optional) Install the package in editable mode to access the `ultralytics` CLI from anywhere:
   ```bash
   pip install -e yolo/yolo-face
   ```
4. Run inference with one of the bundled weights. For example, to perform face detection on an image or video stream:
   ```bash
   yolo task=detect mode=predict model=yolo/yolo-face/yolov11l-face.pt source=path/to/your_media
   ```
   Refer to `yolo/yolo-face/README.md` for additional command variants (training, evaluation, engine export, etc.).

## Next steps
- Capture and organize dual FLIR datasets under `classes/` and `script/` as they become available.
- Add automation scripts for syncing FLIR sensor feeds, preprocessing frames, and launching detection pipelines.
- Track experiment notes and performance metrics so improvements can be shared with collaborators.

