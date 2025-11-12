#!/usr/bin/env python3
"""Quick sanity check that both camera control classes can talk to a FLIR host."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Allow running the script directly from the command line.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.classes.CameraControl import CameraControl  # noqa: E402  # pylint: disable=wrong-import-position
from src.classes.CameraControlAPI import CameraControlAPI  # noqa: E402  # pylint: disable=wrong-import-position
from src.constants import CAMERA_HOSTS, DEFAULT_CAMERA, NEXUS_DEFAULT_PORT  # noqa: E402  # pylint: disable=wrong-import-position


def _safe_call(fn) -> Dict[str, Any]:
    try:
        return {"result": fn(), "error": None}
    except Exception as exc:  # noqa: BLE001
        return {"result": None, "error": str(exc)}


def _run_script_adapter(host: str) -> Dict[str, Any]:
    cam = CameraControl(camera_ip=host)
    return {
        "position": cam.get_degree_pos(),
        "zoom": cam.get_zoom(),
        "speed": cam.get_speed(),
    }


def _run_api_adapter(host: str, port: int, camera_alias: Optional[str]) -> Dict[str, Any]:
    api = CameraControlAPI(camera_alias=camera_alias or DEFAULT_CAMERA, host=host, port=port)
    return {
        "position": api.get_position(),
        "zoom": api.get_zoom(),
        "speed": api.get_speed(),
    }


def test_camera_classes(
    camera_alias: str = DEFAULT_CAMERA,
    host: Optional[str] = None,
    port: int = NEXUS_DEFAULT_PORT,
    run_script_adapter: bool = True,
    run_api_adapter: bool = True,
) -> Dict[str, Any]:
    """Exercise both camera control implementations and return their outputs."""
    resolved_host = host or CAMERA_HOSTS.get(camera_alias)
    if not resolved_host:
        raise ValueError(
            f"Camera alias '{camera_alias}' is unknown and no host override was provided."
        )

    report: Dict[str, Any] = {
        "camera_alias": camera_alias,
        "host": resolved_host,
        "port": port,
    }

    if run_script_adapter:
        report["CameraControl"] = _safe_call(lambda: _run_script_adapter(resolved_host))
    if run_api_adapter:
        report["CameraControlAPI"] = _safe_call(
            lambda: _run_api_adapter(resolved_host, port, camera_alias)
        )
    if not run_script_adapter and not run_api_adapter:
        raise ValueError("At least one adapter must be enabled for testing.")
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test both CameraControl classes against a specified FLIR host."
    )
    parser.add_argument(
        "--camera",
        choices=sorted(CAMERA_HOSTS),
        default=DEFAULT_CAMERA,
        help=f"Camera alias defined in src.constants (default: {DEFAULT_CAMERA}).",
    )
    parser.add_argument(
        "--host",
        help="Override the host/IP instead of using the alias.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=NEXUS_DEFAULT_PORT,
        help=f"HTTP port for the Nexus CGI API (default: {NEXUS_DEFAULT_PORT}).",
    )
    parser.add_argument(
        "--skip-script",
        action="store_true",
        help="Skip the legacy shell-script based CameraControl class.",
    )
    parser.add_argument(
        "--skip-api",
        action="store_true",
        help="Skip the pure Python CameraControlAPI class.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print the JSON response.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        report = test_camera_classes(
            camera_alias=args.camera,
            host=args.host,
            port=args.port,
            run_script_adapter=not args.skip_script,
            run_api_adapter=not args.skip_api,
        )
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    dump = json.dumps(report, indent=2 if args.pretty else None)
    print(dump)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
