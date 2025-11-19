#!/usr/bin/env python3
"""Display both FLIR camera feeds side by side in a single window."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np

# Make repository root importable when the script is executed directly.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.constants import CAMERA_HOSTS  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Display both FLIR camera streams side by side in one window."
    )
    parser.add_argument(
        "--protocol",
        choices=("rtsp", "http", "https"),
        default="rtsp",
        help="Protocol for camera streams (default: rtsp).",
    )
    parser.add_argument(
        "--port",
        type=int,
        help="Override TCP port. Defaults to 8554 for RTSP, 80 for HTTP/S.",
    )
    parser.add_argument(
        "--stream-path",
        default="vis.0",
        help="Stream path (default: vis.0 for FLIR RTSP feeds).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Seconds to wait for first frame from each camera (default: 10s).",
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=1.0,
        help="Scale factor for display window (default: 1.0).",
    )
    parser.add_argument(
        "--camera1",
        choices=sorted(CAMERA_HOSTS),
        default="FLIR1",
        help="First camera alias (default: FLIR1).",
    )
    parser.add_argument(
        "--camera2",
        choices=sorted(CAMERA_HOSTS),
        default="FLIR2",
        help="Second camera alias (default: FLIR2).",
    )
    return parser.parse_args()


def build_stream_url(camera_alias: str, protocol: str, port: Optional[int], stream_path: str) -> str:
    """Build the stream URL for a given camera."""
    host = CAMERA_HOSTS[camera_alias]
    if port is None:
        port = 8554 if protocol == "rtsp" else 80

    sanitized_path = stream_path.lstrip("/")
    base = f"{protocol}://{host}:{port}"

    if sanitized_path:
        return f"{base}/{sanitized_path}"
    return base


def wait_for_first_frame(cap: cv2.VideoCapture, timeout: float, camera_name: str) -> Optional[np.ndarray]:
    """Wait for the first frame from a camera with timeout."""
    start = time.time()
    while time.time() - start < timeout:
        ok, frame = cap.read()
        if ok and frame is not None:
            print(f"[OK] {camera_name} connected successfully.")
            return frame
        time.sleep(0.1)
    return None


def resize_frame(frame: np.ndarray, scale: float) -> np.ndarray:
    """Resize a frame by the given scale factor."""
    if scale == 1.0:
        return frame
    new_width = int(frame.shape[1] * scale)
    new_height = int(frame.shape[0] * scale)
    return cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_AREA)


def combine_frames(frame1: np.ndarray, frame2: np.ndarray) -> np.ndarray:
    """Combine two frames side by side, handling different sizes."""
    # Make sure both frames have the same height
    h1, w1 = frame1.shape[:2]
    h2, w2 = frame2.shape[:2]

    if h1 != h2:
        # Resize both to match the smaller height
        target_height = min(h1, h2)
        if h1 != target_height:
            new_width1 = int(w1 * target_height / h1)
            frame1 = cv2.resize(frame1, (new_width1, target_height))
        if h2 != target_height:
            new_width2 = int(w2 * target_height / h2)
            frame2 = cv2.resize(frame2, (new_width2, target_height))

    # Combine horizontally
    return np.hstack([frame1, frame2])


def add_labels(combined_frame: np.ndarray, camera1_name: str, camera2_name: str) -> np.ndarray:
    """Add camera labels to the combined frame."""
    frame = combined_frame.copy()
    height, width = frame.shape[:2]
    mid_width = width // 2

    # Add text labels
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.8
    font_thickness = 2
    text_color = (0, 255, 0)  # Green
    bg_color = (0, 0, 0)  # Black background

    # Camera 1 label
    text1 = camera1_name
    (text_width1, text_height1), _ = cv2.getTextSize(text1, font, font_scale, font_thickness)
    cv2.rectangle(frame, (10, 10), (10 + text_width1 + 10, 10 + text_height1 + 10), bg_color, -1)
    cv2.putText(frame, text1, (15, 10 + text_height1), font, font_scale, text_color, font_thickness)

    # Camera 2 label
    text2 = camera2_name
    (text_width2, text_height2), _ = cv2.getTextSize(text2, font, font_scale, font_thickness)
    cv2.rectangle(frame, (mid_width + 10, 10), (mid_width + 10 + text_width2 + 10, 10 + text_height2 + 10), bg_color, -1)
    cv2.putText(frame, text2, (mid_width + 15, 10 + text_height2), font, font_scale, text_color, font_thickness)

    return frame


def run_dual_capture(
    url1: str,
    url2: str,
    camera1_name: str,
    camera2_name: str,
    timeout: float,
    scale: float,
) -> None:
    """Capture and display both camera feeds simultaneously."""

    # Open both camera streams
    print(f"Connecting to {camera1_name}: {url1}")
    cap1 = cv2.VideoCapture(url1, cv2.CAP_FFMPEG)

    print(f"Connecting to {camera2_name}: {url2}")
    cap2 = cv2.VideoCapture(url2, cv2.CAP_FFMPEG)

    if not cap1.isOpened():
        raise RuntimeError(f"Unable to open stream for {camera1_name}: {url1}")

    if not cap2.isOpened():
        cap1.release()
        raise RuntimeError(f"Unable to open stream for {camera2_name}: {url2}")

    try:
        # Wait for first frames
        print(f"\nWaiting for first frames (timeout: {timeout}s)...")
        frame1 = wait_for_first_frame(cap1, timeout, camera1_name)
        if frame1 is None:
            raise TimeoutError(f"No frames received from {camera1_name} within {timeout}s.")

        frame2 = wait_for_first_frame(cap2, timeout, camera2_name)
        if frame2 is None:
            raise TimeoutError(f"No frames received from {camera2_name} within {timeout}s.")

        # Create display window
        window_name = "Dual FLIR Camera Feed"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

        print("\n[SUCCESS] Both cameras connected!")
        print("Press 'q' or ESC to exit.")
        print("Press 's' to save a snapshot.")

        frame_count = 0
        start_time = time.time()
        snapshot_count = 0

        while True:
            # Read frames
            ok1, frame1 = cap1.read()
            ok2, frame2 = cap2.read()

            if not ok1:
                print(f"[WARNING] Failed to read frame from {camera1_name}")
                continue

            if not ok2:
                print(f"[WARNING] Failed to read frame from {camera2_name}")
                continue

            # Combine frames
            combined = combine_frames(frame1, frame2)

            # Add labels
            labeled = add_labels(combined, camera1_name, camera2_name)

            # Apply scaling
            display_frame = resize_frame(labeled, scale)

            # Show frame
            cv2.imshow(window_name, display_frame)

            # Handle keyboard input
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord('q')):  # ESC or 'q'
                print("\nUser requested exit.")
                break
            elif key == ord('s'):  # Save snapshot
                snapshot_count += 1
                filename = f"dual_camera_snapshot_{snapshot_count:03d}.jpg"
                cv2.imwrite(filename, labeled)
                print(f"[SAVED] Snapshot saved as {filename}")

            frame_count += 1

            # Print stats every 30 frames
            if frame_count % 30 == 0:
                elapsed = time.time() - start_time
                fps = frame_count / elapsed
                print(f"[INFO] Frames: {frame_count}, FPS: {fps:.1f}")

    finally:
        cap1.release()
        cap2.release()
        cv2.destroyAllWindows()
        print(f"\n[INFO] Total frames captured: {frame_count}")


def main() -> int:
    args = parse_args()

    try:
        # Build stream URLs
        url1 = build_stream_url(args.camera1, args.protocol, args.port, args.stream_path)
        url2 = build_stream_url(args.camera2, args.protocol, args.port, args.stream_path)

        # Run dual capture
        run_dual_capture(
            url1=url1,
            url2=url2,
            camera1_name=args.camera1,
            camera2_name=args.camera2,
            timeout=args.timeout,
            scale=args.scale,
        )
        return 0

    except KeyboardInterrupt:
        print("\nInterrupted by user.", file=sys.stderr)
        return 130

    except Exception as exc:
        print(f"\n[ERROR] {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
