"""
Centralised configuration for dual FLIR camera control utilities.

`CAMERA_HOSTS` maps friendly camera identifiers (e.g. "FLIR1") to their IP
addresses and `DEFAULT_CAMERA` is used when no camera is specified.

The `CAMERA_COMMANDS` dictionary defines the HTTP actions supported by the
master control script. Each entry describes the CGI action, any additional
static query parameters, and the dynamic parameters that must be supplied when
calling the command.

Example
-------
>>> from src.constants import CAMERA_COMMANDS
>>> CAMERA_COMMANDS["set_zoom"]["params"]
[{'name': 'Magnification', 'type': float, 'help': 'Target zoom magnification.'}]
"""

from __future__ import annotations

from typing import Any, Dict

FLIR1_IP = "169.254.80.109"
FLIR2_IP = "169.254.50.183"

# Default CGI host configuration for DLTV/PTZ controls.
DEFAULT_CAMERA = "FLIR2"
CAMERA_HOSTS: Dict[str, str] = {
    "FLIR1": FLIR1_IP,
    "FLIR2": FLIR2_IP,
}

NEXUS_DEFAULT_IP = CAMERA_HOSTS[DEFAULT_CAMERA]
NEXUS_DEFAULT_PORT = 80
NEXUS_CGI_PATH = "/Nexus.cgi"
TOKEN_OVERRIDE_PARAMS = {
    "tokenoverride": "1",
    "_": "0",
}

# Parameter specification type alias to keep type hints lightweight.
ParameterSpec = Dict[str, Any]

# Command specification structure. Each command requires an action name and can
# optionally include static params added automatically to the request and a list
# of dynamic parameters (with types) the user must supply on the CLI.
CommandSpec = Dict[str, Any]

CAMERA_COMMANDS: Dict[str, CommandSpec] = {
    "get_zoom": {
        "action": "DLTVFOVMagnificationGet",
        "description": "Return the current zoom magnification.",
        "params": [],
    },
    "get_zoom_fov": {
        "action": "DLTVZoomDegreesGet",
        "description": "Return the current zoom field-of-view in degrees.",
        "params": [],
    },
    "set_zoom": {
        "action": "DLTVFOVMagnificationSet",
        "description": "Set zoom magnification to a specific value.",
        "params": [
            {
                "name": "Magnification",
                "type": float,
                "help": "Target zoom magnification.",
            },
        ],
    },
    "auto_focus": {
        "action": "DLTVAutoFocusPush",
        "description": "Trigger an autofocus operation.",
        "params": [],
    },
    "get_speed": {
        "action": "PTSpeedGet",
        "description": "Fetch the current azimuth/elevation speed configuration.",
        "params": [],
    },
    "set_speed": {
        "action": "PTSpeedModeSet",
        "description": "Update azimuth and elevation speed settings.",
        "params": [
            {
                "name": "Azimuth_Speed",
                "type": int,
                "help": "Desired azimuth speed setting.",
            },
            {
                "name": "Elevation_Speed",
                "type": int,
                "help": "Desired elevation speed setting.",
            },
        ],
    },
    "get_position": {
        "action": "PTAzimuthElevationGet",
        "description": "Retrieve the current azimuth/elevation angles.",
        "params": [],
    },
    "center": {
        "action": "PTAzimuthElevationOnScreenSet",
        "description": "Center the camera on a screen coordinate (X/Y).",
        "static_params": {
            "Active_cam": "0",
            "Cam_type": "4",
            "Cam_id": "0",
        },
        "params": [
            {
                "name": "ScreenX",
                "type": float,
                "help": "Horizontal screen coordinate.",
            },
            {
                "name": "ScreenY",
                "type": float,
                "help": "Vertical screen coordinate.",
            },
        ],
    },
}
