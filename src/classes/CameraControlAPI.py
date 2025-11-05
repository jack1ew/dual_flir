import json
import time
from typing import Any, Dict, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from src.constants import CAMERA_HOSTS, DEFAULT_CAMERA, NEXUS_CGI_PATH, NEXUS_DEFAULT_PORT
from src.script import camera_control


class CameraControlAPI:
    """Python implementation that reuses the master command registry instead of shell scripts."""

    def __init__(
        self,
        camera_alias: str = DEFAULT_CAMERA,
        host: Optional[str] = None,
        port: int = NEXUS_DEFAULT_PORT,
        session_timeout: float = 120.0,
        request_timeout: float = 5.0,
    ) -> None:
        self.camera_alias = camera_alias
        self.port = port
        self._host_override = host
        self.session_timeout = session_timeout
        self.request_timeout = request_timeout

        self.session_id: Optional[str] = None
        self._last_auth = 0.0

    # ------------------------------------------------------------------
    # Host / session management helpers
    # ------------------------------------------------------------------
    @property
    def host(self) -> str:
        if self._host_override:
            return self._host_override
        if self.camera_alias not in CAMERA_HOSTS:
            available = ", ".join(sorted(CAMERA_HOSTS))
            raise ValueError(
                f"Unknown camera alias '{self.camera_alias}'. Known aliases: {available}"
            )
        return CAMERA_HOSTS[self.camera_alias]

    def set_camera(self, camera_alias: Optional[str] = None, host: Optional[str] = None) -> None:
        """Switch to a different camera alias or explicit host."""
        if camera_alias is not None:
            self.camera_alias = camera_alias
        if host is not None:
            self._host_override = host
        self.invalidate_session()

    def invalidate_session(self) -> None:
        """Force the next command to re-authenticate."""
        self.session_id = None
        self._last_auth = 0.0

    def _session_expired(self) -> bool:
        return (time.time() - self._last_auth) > self.session_timeout

    def _base_url(self) -> str:
        return f"http://{self.host}:{self.port}{NEXUS_CGI_PATH}"

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------
    def authenticate(self, force: bool = False) -> bool:
        if not force and self.session_id and not self._session_expired():
            return True

        auth_url = f"{self._base_url()}?action=SERVERWhoAmI"
        request = Request(auth_url)
        try:
            with urlopen(request, timeout=self.request_timeout) as response:
                payload = response.read().decode("utf-8")
        except (HTTPError, URLError) as exc:
            print(f"Authentication failed: {exc}")
            self.invalidate_session()
            return False

        try:
            data = json.loads(payload)
            session = data.get("SERVERWhoAmI", {}).get("Id")
        except json.JSONDecodeError as exc:
            print(f"Authentication failed: invalid JSON ({exc})")
            self.invalidate_session()
            return False

        if not session:
            print("Authentication failed: session ID missing in response.")
            self.invalidate_session()
            return False

        self.session_id = session
        self._last_auth = time.time()
        return True

    # ------------------------------------------------------------------
    # Command execution
    # ------------------------------------------------------------------
    def execute(self, command_name: str, **params: Any) -> Dict[str, Any]:
        if not self.authenticate():
            raise RuntimeError("Unable to authenticate before executing command.")

        parsed_command = camera_control.load_command(command_name)
        expected = {spec["name"] for spec in parsed_command.param_specs}

        coerced: Dict[str, str] = {}
        for spec in parsed_command.param_specs:
            name = spec["name"]
            required = spec.get("required", True)
            if name not in params:
                if required and "default" not in spec:
                    raise ValueError(
                        f"Missing required parameter '{name}' for command '{command_name}'."
                    )
                if "default" in spec:
                    coerced[name] = str(spec["default"])
                continue
            coerced[name] = camera_control.coerce_param_value(name, str(params[name]), spec)

        extras = set(params) - expected
        if extras:
            extras_str = ", ".join(sorted(extras))
            raise ValueError(
                f"Unexpected parameter(s) for '{command_name}': {extras_str}."
            )

        query = camera_control.build_query(
            parsed_command,
            session=self.session_id,
            dynamic_params=coerced,
            include_token_params=True,
        )

        return camera_control.issue_request(
            self._base_url(),
            query,
            timeout=self.request_timeout,
        )

    # ------------------------------------------------------------------
    # Convenience wrappers mirroring the legacy CameraControl API
    # ------------------------------------------------------------------
    def get_zoom(self) -> Optional[float]:
        try:
            result = self.execute("get_zoom")
        except RuntimeError:
            return None
        except ValueError as exc:
            print(f"get_zoom error: {exc}")
            return None

        payload = result.get("DLTVFOVMagnificationGet")
        if not payload:
            return None
        magnification = payload.get("Magnification")
        return float(magnification) if magnification is not None else None

    def set_zoom(self, magnification: float) -> bool:
        try:
            self.execute("set_zoom", Magnification=magnification)
            return True
        except (RuntimeError, ValueError) as exc:
            print(f"set_zoom error: {exc}")
            return False

    def get_speed(self) -> Optional[Tuple[float, float]]:
        try:
            result = self.execute("get_speed")
        except (RuntimeError, ValueError) as exc:
            print(f"get_speed error: {exc}")
            return None

        payload = result.get("PTSpeedGet")
        if not payload:
            return None
        az_speed = payload.get("Azimuth_Speed")
        el_speed = payload.get("Elevation_Speed")
        if az_speed is None or el_speed is None:
            return None
        return float(az_speed), float(el_speed)

    def set_speed(self, azimuth_speed: int, elevation_speed: int) -> bool:
        try:
            self.execute(
                "set_speed",
                Azimuth_Speed=azimuth_speed,
                Elevation_Speed=elevation_speed,
            )
            return True
        except (RuntimeError, ValueError) as exc:
            print(f"set_speed error: {exc}")
            return False

    def get_position(self) -> Optional[Tuple[float, float]]:
        try:
            result = self.execute("get_position")
        except (RuntimeError, ValueError) as exc:
            print(f"get_position error: {exc}")
            return None

        payload = result.get("PTAzimuthElevationGet")
        if not payload:
            return None
        azimuth = payload.get("Azimuth")
        elevation = payload.get("Elevation")
        if azimuth is None or elevation is None:
            return None
        return float(azimuth), float(elevation)

    def center(self, screen_x: float, screen_y: float) -> bool:
        try:
            self.execute("center", ScreenX=screen_x, ScreenY=screen_y)
            return True
        except (RuntimeError, ValueError) as exc:
            print(f"center error: {exc}")
            return False

    def auto_focus(self) -> bool:
        try:
            self.execute("auto_focus")
            return True
        except (RuntimeError, ValueError) as exc:
            print(f"auto_focus error: {exc}")
            return False
