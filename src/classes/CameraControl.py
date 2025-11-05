import json
import subprocess
import time
from pathlib import Path
from typing import Optional

from src.constants import FLIR2_IP


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "script"


def _resolve_script(script_path: Optional[str], fallback_name: str) -> str:
    """Resolve a script path relative to the script directory when needed."""
    if script_path:
        candidate = Path(script_path)
        if candidate.is_file():
            return str(candidate.resolve())
        candidate = SCRIPT_DIR / candidate.name
        if candidate.is_file():
            return str(candidate.resolve())
        return script_path  # Fall back to original string; let subprocess surface errors.
    return str((SCRIPT_DIR / fallback_name).resolve())


class CameraControl:
    def __init__(
        self,
        auth_script: Optional[str] = None,
        get_degree_script: Optional[str] = None,
        get_zoom_script: Optional[str] = None,
        get_speed_script: Optional[str] = None,
        move_script: Optional[str] = None,
        set_zoom_script: Optional[str] = None,
        camera_ip: Optional[str] = None,
    ):

        # Scripts for camera control
        self.AUTHENTICATE_SCRIPT = _resolve_script(auth_script, "authenticate.sh")
        self.GET_DEGREE = _resolve_script(get_degree_script, "get_degree.sh")
        self.GET_ZOOM = _resolve_script(get_zoom_script, "get_zoom.sh")
        self.SET_ZOOM = _resolve_script(set_zoom_script, "set_zoom.sh")
        self.MOVE_SCRIPT = _resolve_script(move_script, "move_to_pos.sh")
        self.GET_SPEED = _resolve_script(get_speed_script, "get_speed.sh")

        # Network configuration
        self.camera_ip = camera_ip or FLIR2_IP

        # Session and state variables
        self.session_id: Optional[str] = None
        self.last_auth_time = 0.0
        # Most camera sessions expire after 60-300 seconds of inactivity.
        self.SESSION_TIMEOUT = 120.0

    def set_camera_ip(self, ip_address: str) -> None:
        """Update the target camera IP address."""
        if not ip_address:
            raise ValueError("Camera IP address cannot be empty.")
        if ip_address != self.camera_ip:
            self.camera_ip = ip_address
            # Force re-authentication on next call for the new camera.
            self.session_id = None
            self.last_auth_time = 0.0

    def _is_session_expired(self):
        """Checks if the session is likely expired based on time."""
        return (time.time() - self.last_auth_time) > self.SESSION_TIMEOUT

    def authenticate(self, force_auth=False):
        """
        Authenticates with the FLIR camera to obtain a session ID.
        It will only re-authenticate if forced or if the session is expired.
        """
        if not force_auth and self.session_id and not self._is_session_expired():
            # If we have a session ID and it's not expired, do nothing.
            return True

        print("Session expired or forced. Running authentication script...")
        try:
            process_auth = subprocess.Popen(
                [self.AUTHENTICATE_SCRIPT, self.camera_ip],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process_auth.communicate(timeout=15)

            if process_auth.returncode != 0:
                print(f"Authentication script failed! Stderr: {stderr.strip()}")
                self.session_id = None
                return False

            self.session_id = stdout.strip()
            if not self.session_id:
                print("Failed to get session ID from authenticate script. Stdout was empty.")
                return False

            # --- IMPORTANT: Update the authentication timestamp ---
            self.last_auth_time = time.time()
            print(f"Obtained new Session ID: {self.session_id}")
            return True
        except Exception as e:
            print(f"An exception occurred during authentication: {e}")
            self.session_id = None
            return False

    def get_degree_pos(self):
        """
        Fetches the camera's position, with re-authentication on failure.
        """
        # --- MODIFIED: Proactive session check ---
        if not self.authenticate():
            return None, None

        for attempt in range(2):
            try:
                command_to_get = [self.GET_DEGREE, self.camera_ip, self.session_id]
                json_output = subprocess.run(command_to_get, capture_output=True, text=True, check=True)
                output_str = json_output.stdout
                json_start_index = output_str.find('{')
                if json_start_index == -1: continue
                data = json.loads(output_str[json_start_index:])

                azimuth = data.get('PTAzimuthElevationGet', {}).get('Azimuth')
                elevation = data.get('PTAzimuthElevationGet', {}).get('Elevation')
                return azimuth, elevation
            except subprocess.CalledProcessError as e:
                print(f"Get position failed on attempt {attempt + 1}. Stderr: {e.stderr.strip()}")
                if attempt == 0:
                    # Force re-authentication on the first failure
                    if not self.authenticate(force_auth=True): return None, None
                else:
                    return None, None # Give up after the second attempt
            except Exception as e:
                print(f"An unexpected error occurred in get_degree_pos: {e}")
                return None, None

    def move_camera_to_absolute_pos(self, target_az, target_el, speed_az=180, speed_el=180):
        """
        Moves the camera, with re-authentication on failure.
        """
        # --- MODIFIED: Proactive session check ---
        if not self.authenticate():
            return False

        for attempt in range(2):
            try:
                command = [
                    self.MOVE_SCRIPT,
                    self.camera_ip,
                    self.session_id,
                    f"{target_az:.2f}",
                    f"{target_el:.2f}",
                    f"{speed_az:.2f}",
                    f"{speed_el:.2f}",
                ]
                subprocess.run(command, capture_output=True, text=True, check=True)
                return True
            except subprocess.CalledProcessError as e:
                print(f"Move command failed on attempt {attempt + 1}. Stderr: {e.stderr.strip()}")
                if attempt == 0:
                    if not self.authenticate(force_auth=True): return False
                else:
                    return False
            except Exception as e:
                print(f"An unexpected error occurred in move_camera_to_absolute_pos: {e}")
                return False

    def get_zoom(self):
        """
        Fetches the camera's zoom, with re-authentication on failure.
        """
        # --- MODIFIED: Proactive session check ---
        if not self.authenticate():
            return None

        for attempt in range(2):
            try:
                command = [self.GET_ZOOM, self.camera_ip, self.session_id]
                process_result = subprocess.run(command, capture_output=True, text=True, check=True)
                output_str = process_result.stdout
                json_start_index = output_str.find('{')
                if json_start_index == -1:
                    print(f"Error: No JSON object found in script output on attempt {attempt + 1}.")
                    continue

                json_str = output_str[json_start_index:]
                data = json.loads(json_str)
                current_zoom = data.get('DLTVFOVMagnificationGet', {}).get('Magnification')
                if current_zoom is None: return None
                return float(current_zoom)
            except subprocess.CalledProcessError as e:
                print(f"Get zoom failed on attempt {attempt + 1}. Stderr: {e.stderr.strip()}")
                if attempt == 0:
                    if not self.authenticate(force_auth=True): return None
                else:
                    return None
            except Exception as e:
                print(f"An unexpected error occurred in get_zoom: {e}")
                return None

    def set_zoom(self, zoom):
        """
        Sets the zoom of the camera
        """
        # --- MODIFIED: Proactive session check ---
        if not self.authenticate():
            return False

        for attempt in range(2):
            try:
                command = [self.SET_ZOOM, self.camera_ip, self.session_id, f"{float(zoom):.2f}"]
                subprocess.run(command, capture_output=True, text=True, check=True)
                return True
            except subprocess.CalledProcessError as e:
                print(f"Set zoom failed on attempt {attempt + 1}. Stderr: {e.stderr.strip()}")
                if attempt == 0:
                    if not self.authenticate(force_auth=True): return False
                else:
                    return False
            except Exception as e:
                print(f"An unexpected error occurred in set_zoom: {e}")
                return False

    # --- Unchanged helper methods below ---

    def calculate_screen_offset_degrees(self, pixel_x, pixel_y, screen_width, screen_height, horizontal_fov, vertical_fov):
        '''
        Find offset of the detected target
        '''
        normalized_x = (2 * pixel_x / screen_width) - 1
        normalized_y = 1 - (2 * pixel_y / screen_height)
        angle_x = normalized_x * (horizontal_fov / 2)
        angle_y = normalized_y * (vertical_fov / 2)
        return angle_x, angle_y

    def calculate_absolute_target_pos(self, pixel_x, pixel_y, current_h_fov, current_v_fov, screen_width, screen_height, camera_az, camera_el):
        '''
        Add offset to the current absolute position of the center of the screen
        '''
        if camera_az is None or camera_el is None:
            return None, None
        offset_az, offset_el = self.calculate_screen_offset_degrees(pixel_x, pixel_y, screen_width, screen_height, current_h_fov, current_v_fov)
        final_az = (camera_az + offset_az + 360) % 360
        final_el = camera_el + offset_el
        return final_az, final_el

    def get_speed(self):
        """
        Fetches the camera's speed, with re-authentication on failure.
        """
        if not self.authenticate():
            return None

        for attempt in range(2):
            try:
                command = [self.GET_SPEED, self.camera_ip, self.session_id]
                process_result = subprocess.run(command, capture_output=True, text=True, check=True)
                output_str = process_result.stdout
                json_start_index = output_str.find('{')
                if json_start_index == -1:
                    print(f"Error: No JSON object found in script output on attempt {attempt + 1}.")
                    continue # This will trigger the re-auth on the first attempt

                json_str = output_str[json_start_index:]
                data = json.loads(json_str)
                current_az_speed = data.get('PTSpeedGet', {}).get('Azimuth_Speed')
                current_el_speed = data.get('PTSpeedGet', {}).get('Elevation_Speed')
                if current_az_speed is None or current_el_speed is None: return None
                return float(current_az_speed), float(current_el_speed) # Success
            except subprocess.CalledProcessError as e:
                print(f"Get speed failed on attempt {attempt + 1}. Stderr: {e.stderr.strip()}")
                if attempt == 0:
                    if not self.authenticate(force_auth=True): return None
                else:
                    return None
            except Exception as e:
                print(f"An unexpected error occurred in get_speed: {e}")
                return None
