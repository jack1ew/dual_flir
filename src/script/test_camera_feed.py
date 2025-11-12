#!/usr/bin/env python3
"""Quick OpenCV-based health check for FLIR video feeds."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Optional, Union

import cv2

# Make repository root importable when the script is executed directly.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.constants import CAMERA_HOSTS, DEFAULT_CAMERA  # noqa: E402  # pylint: disable=wrong-import-position


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test a FLIR camera stream by grabbing frames via OpenCV."
    )
    parser.add_argument(
        "--stream-url",
        help="Full OpenCV-compatible source (RTSP/HTTP/file). Overrides camera/host options.",
    )
    parser.add_argument(
        "--camera",
        choices=sorted(CAMERA_HOSTS),
        default="FLIR1",
        help=f"Camera alias defined in src.constants (default: FLIR1, repo default is {DEFAULT_CAMERA}).",
    )
    parser.add_argument(
        "--protocol",
        choices=("rtsp", "http", "https"),
        default="rtsp",
        help="Protocol used when building a URL from the camera alias (default: rtsp).",
    )
    parser.add_argument(
        "--port",
        type=int,
        help="Override TCP port used for the stream. Defaults to 8554 for RTSP and 80 for HTTP/S.",
    )
    parser.add_argument(
        "--stream-path",
        default="vis.0",
        help="Path appended to the host when constructing the stream URL (default: vis.0 for FLIR RTSP feeds).",
    )
    parser.add_argument(
        "--device-index",
        type=int,
        help="Use a local capture device instead of an IP stream (e.g., 0 for /dev/video0).",
    )
    parser.add_argument(
        "--frame-count",
        type=int,
        default=120,
        help="Number of frames to read before declaring success (default: 120).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="Seconds to wait for the first frame before failing (default: 5s).",
    )
    parser.add_argument(
        "--display",
        action="store_true",
        help="Render the incoming frames in an OpenCV window (press q or ESC to exit).",
    )
    return parser.parse_args()


def resolve_source(args: argparse.Namespace) -> Union[str, int]:
    if args.stream_url:
        return args.stream_url

    if args.device_index is not None:
        return args.device_index

    host = CAMERA_HOSTS[args.camera]
    port = args.port
    if port is None:
        port = 8554 if args.protocol == "rtsp" else 80

    sanitized_path = args.stream_path.lstrip("/")
    base = f"{args.protocol}://{host}"
    if port:
        base = f"{base}:{port}"

    if sanitized_path:
        return f"{base}/{sanitized_path}"
    return base


def wait_for_first_frame(cap: cv2.VideoCapture, timeout: float) -> Optional[cv2.Mat]:
    start = time.time()
    while time.time() - start < timeout:
        ok, frame = cap.read()
        if ok:
            return frame
        time.sleep(0.1)
    return None


def run_capture(source: Union[str, int], frame_count: int, timeout: float, display: bool) -> None:
    backend = cv2.CAP_FFMPEG if isinstance(source, str) and source.startswith(("rtsp://", "http://", "https://")) else cv2.CAP_ANY
    cap = cv2.VideoCapture(source, backend)
    if not cap.isOpened():
        raise RuntimeError(f"Unable to open stream '{source}'.")

    try:
        first_frame = wait_for_first_frame(cap, timeout)
        if first_frame is None:
            raise TimeoutError(f"No frames received within {timeout:.1f}s.")

        start_time = time.time()
        frames_seen = 1

        if display:
            cv2.imshow("FLIR feed", first_frame)

        print(f"[OK] Connected to {source}. Starting capture...")

        while frames_seen < frame_count:
            ok, frame = cap.read()
            if not ok:
                raise RuntimeError("Frame grab failed; stream may have dropped.")

            frames_seen += 1
            if display:
                cv2.imshow("FLIR feed", frame)
                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord("q")):  # ESC or q
                    print("User requested exit.")
                    break

            if frames_seen % 30 == 0:
                elapsed = time.time() - start_time + 1e-9
                fps = frames_seen / elapsed
                print(f"[INFO] Captured {frames_seen}/{frame_count} frames (approx {fps:.1f} FPS).")

        print(f"[SUCCESS] Stream healthy. Frames read: {frames_seen}.")
    finally:
        cap.release()
        if display:
            cv2.destroyAllWindows()


def main() -> int:
    args = parse_args()
    try:
        source = resolve_source(args)
        run_capture(source, args.frame_count, args.timeout, args.display)
        return 0
    except KeyboardInterrupt:
        print("Interrupted by user.", file=sys.stderr)
        return 130
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
