#!/usr/bin/env python3
"""Generic camera control utility for Nexus CGI compatible FLIR cameras.

Example usage:
    python src/script/camera_control.py set_zoom --session 1234 Magnification=2.0
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

# Ensure repository root is on sys.path when executed directly.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.constants import (  # noqa: E402  # pylint: disable=wrong-import-position
    CAMERA_HOSTS,
    CAMERA_COMMANDS,
    DEFAULT_CAMERA,
    NEXUS_CGI_PATH,
    NEXUS_DEFAULT_PORT,
    TOKEN_OVERRIDE_PARAMS,
)


@dataclass
class ParsedCommand:
    name: str
    action: str
    description: str
    static_params: Dict[str, Any]
    param_specs: List[Dict[str, Any]]


def resolve_host(host: Optional[str], camera_alias: Optional[str]) -> str:
    if host:
        return host

    alias = camera_alias or DEFAULT_CAMERA
    if alias in CAMERA_HOSTS:
        return CAMERA_HOSTS[alias]

    available = ", ".join(sorted(CAMERA_HOSTS))
    raise ValueError(
        f"Unknown camera alias '{alias}'. Known aliases: {available}"
    )


def load_command(command_name: str) -> ParsedCommand:
    spec = CAMERA_COMMANDS.get(command_name)
    if spec is None:
        available = ", ".join(sorted(CAMERA_COMMANDS))
        raise ValueError(f"Unknown command '{command_name}'. Available: {available}")

    return ParsedCommand(
        name=command_name,
        action=spec["action"],
        description=spec.get("description", ""),
        static_params=spec.get("static_params", {}),
        param_specs=list(spec.get("params", [])),
    )


def parse_param_pairs(pairs: Iterable[str]) -> Dict[str, str]:
    parsed: Dict[str, str] = {}
    for raw in pairs:
        if "=" not in raw:
            raise ValueError(f"Parameter '{raw}' must be in key=value format.")
        key, value = raw.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"Invalid parameter '{raw}' (empty key).")
        parsed[key] = value
    return parsed


def coerce_param_value(name: str, value: str, spec: Dict[str, Any]) -> str:
    converter = spec.get("type", str)
    if converter is bool:
        truthy = {"1", "true", "t", "yes", "y", "on"}
        falsy = {"0", "false", "f", "no", "n", "off"}
        lower_val = value.lower()
        if lower_val in truthy:
            return "1"
        if lower_val in falsy:
            return "0"
        raise ValueError(
            f"Parameter '{name}' expects a boolean value. "
            f"Supported inputs: {sorted(truthy | falsy)}"
        )

    try:
        converted = converter(value)
    except Exception as exc:
        typename = getattr(converter, "__name__", str(converter))
        raise ValueError(f"Unable to convert '{name}'='{value}' to {typename}") from exc

    if isinstance(converted, float):
        return f"{converted:.10g}"
    return str(converted)


def build_query(
    command: ParsedCommand,
    session: str,
    dynamic_params: Dict[str, str],
    include_token_params: bool = True,
) -> Dict[str, str]:
    query: Dict[str, str] = {
        "session": session,
        "action": command.action,
    }
    query.update(command.static_params)
    query.update(dynamic_params)
    if include_token_params:
        query.update(TOKEN_OVERRIDE_PARAMS)
    return query


def issue_request(
    url_base: str,
    query_params: Dict[str, str],
    timeout: float,
    method: str = "GET",
) -> Dict[str, Any]:
    encoded_query = urlencode(query_params)
    full_url = f"{url_base}?{encoded_query}"

    request = Request(full_url, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8")
    except HTTPError as exc:
        raise RuntimeError(f"HTTP error {exc.code} from camera: {exc.reason}") from exc
    except URLError as exc:
        raise RuntimeError(f"Failed to reach camera: {exc.reason}") from exc

    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return {"raw": payload}


def wait_for_host(host: str, port: int, retries: int, delay: float) -> None:
    if retries <= 0:
        return

    import socket

    for attempt in range(1, retries + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(delay)
            try:
                if sock.connect_ex((host, port)) == 0:
                    return
            except OSError:
                pass
        time.sleep(delay)

    raise RuntimeError(f"Camera at {host}:{port} not reachable after {retries} attempts.")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Send camera control commands via the Nexus CGI API."
    )
    parser.add_argument(
        "command",
        help="Name of the command defined in constants.CAMERA_COMMANDS.",
    )
    parser.add_argument(
        "--session",
        required=True,
        help="Active session identifier retrieved from authenticate.sh.",
    )
    parser.add_argument(
        "--camera",
        choices=sorted(CAMERA_HOSTS),
        help=f"Camera alias defined in constants.CAMERA_HOSTS (default: {DEFAULT_CAMERA}).",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="Camera host/IP address. Overrides --camera when provided.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=NEXUS_DEFAULT_PORT,
        help=f"Camera HTTP port (default: {NEXUS_DEFAULT_PORT}).",
    )
    parser.add_argument(
        "--path",
        default=NEXUS_CGI_PATH,
        help=f"CGI path component (default: {NEXUS_CGI_PATH}).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="HTTP timeout in seconds (default: 5).",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=0,
        help="Number of connection retries before giving up.",
    )
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=1.0,
        help="Seconds to wait between retries (default: 1).",
    )
    parser.add_argument(
        "--no-token-override",
        action="store_true",
        help="Do not append the default token override query parameters.",
    )
    parser.add_argument(
        "--print-url",
        action="store_true",
        help="Print the URL that will be requested before executing.",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Print raw response payload instead of parsed JSON.",
    )
    parser.add_argument(
        "params",
        nargs="*",
        help="Command specific parameters in key=value form (e.g. Magnification=2.0).",
    )

    args = parser.parse_args(argv)

    try:
        command = load_command(args.command)
    except ValueError as exc:
        parser.error(str(exc))

    try:
        host = resolve_host(args.host, args.camera)
    except ValueError as exc:
        parser.error(str(exc))

    provided_params = parse_param_pairs(args.params)
    coerced_params: Dict[str, str] = {}

    for spec in command.param_specs:
        name = spec["name"]
        required = spec.get("required", True)

        if name not in provided_params:
            if required and "default" not in spec:
                parser.error(
                    f"Missing required parameter '{name}' for command '{command.name}'."
                )
            if "default" in spec:
                coerced_params[name] = str(spec["default"])
            continue

        value = provided_params.pop(name)
        coerced_params[name] = coerce_param_value(name, value, spec)

    if provided_params:
        extras = ", ".join(provided_params.keys())
        parser.error(
            f"Unexpected parameters for '{command.name}': {extras}. "
            "Check constants.CAMERA_COMMANDS for supported names."
        )

    base_url = f"http://{host}:{args.port}{args.path}"
    query_params = build_query(
        command,
        session=args.session,
        dynamic_params=coerced_params,
        include_token_params=not args.no_token_override,
    )

    if args.print_url:
        encoded_query = urlencode(query_params)
        print(f"{base_url}?{encoded_query}")

    if args.retries > 0:
        wait_for_host(host, args.port, args.retries, args.retry_delay)

    try:
        response = issue_request(base_url, query_params, timeout=args.timeout)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.raw or "raw" in response:
        print(response.get("raw") if isinstance(response, dict) else response)
    else:
        print(json.dumps(response, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
