"""Native camera previews with one owner per physical camera.

The preview uses LeRobot's camera driver and settings. Multiple browser tabs
share one capture thread. Starting a physical session closes idle captures
under the same lock that guards new preview requests.
"""

from __future__ import annotations

import contextlib
import logging
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

from .camera_rotation import camera_rotation

logger = logging.getLogger(__name__)
_device_provider: Callable[[], list[dict[str, Any]]] | None = None


class CameraPreviewError(RuntimeError):
    def __init__(self, message: str, status_code: int = 503):
        super().__init__(message)
        self.status_code = status_code


def set_device_provider(provider: Callable[[], list[dict[str, Any]]]) -> None:
    """Register the server's native enumeration, never browser device names."""
    global _device_provider
    _device_provider = provider


def resolve_camera_index(index: int, device_id: str | None = None) -> int:
    """Resolve a saved native identity against the current OpenCV index order.

    Legacy profiles without an identity use their explicit camera index. A
    missing saved identity is an error, rather than silently opening another
    camera after a USB reconnect changes the order.
    """
    if not device_id:
        return index
    if _device_provider is None:
        raise CameraPreviewError("Native camera discovery is unavailable. Refresh camera settings.", 422)
    matches = [cam for cam in _device_provider() if cam.get("unique_id") == device_id]
    if len(matches) != 1:
        raise CameraPreviewError("The selected camera is disconnected. Refresh camera settings.", 422)
    return int(matches[0]["index"])


def resolve_camera_sources(cameras: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Return recorder settings with stable identities resolved once per start."""
    resolved = {}
    for role, config in cameras.items():
        config = dict(config)
        config["camera_index"] = resolve_camera_index(
            config.get("camera_index", 0), config.get("backend_device_id")
        )
        resolved[role] = config
    return resolved


@dataclass
class _Capture:
    camera: Any
    config: Any
    subscribers: int = 0
    closed: bool = False


class PreviewLease:
    """A browser's share of a capture, released once even on cancellation."""

    def __init__(self, manager: CameraPreviewManager, key: int, capture: _Capture):
        self.manager = manager
        self.key = key
        self.capture = capture
        self.released = False

    def jpeg(self) -> bytes | None:
        import cv2

        with self.manager._lock:
            if self.released or self.capture.closed:
                return None
            frame = self.capture.camera.read_latest()
        # OpenCVCamera returns already-rotated RGB, just like the recorder.
        ok, image = cv2.imencode(".jpg", cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
        if not ok:
            raise CameraPreviewError("The camera frame could not be displayed.")
        return image.tobytes()

    def release(self) -> None:
        with self.manager._lock:
            if self.released:
                return
            self.released = True
            self.capture.subscribers -= 1
            if self.capture.subscribers == 0 and not self.capture.closed:
                self.manager._close(self.key, self.capture)


class CameraPreviewManager:
    def __init__(
        self,
        busy: Callable[[], bool] = lambda: False,
        camera_factory: Callable[[Any], Any] | None = None,
    ):
        self.busy = busy
        self.camera_factory = camera_factory
        self._lock = threading.RLock()
        self._captures: dict[int, _Capture] = {}

    def acquire(self, config: Any) -> PreviewLease:
        from lerobot.cameras.opencv import OpenCVCamera

        key = config.index_or_path
        with self._lock:
            if self.busy():
                raise CameraPreviewError("A robot session owns the cameras. Stop it before previewing.", 409)
            capture = self._captures.get(key)
            if capture is not None and capture.config != config:
                # A settings change invalidates the old stream before reopening
                # the same physical source. Never create two competing handles.
                self._close(key, capture)
                capture = None
            if capture is None:
                camera = (self.camera_factory or OpenCVCamera)(config)
                try:
                    camera.connect()
                    camera.read_latest()
                except Exception as exc:
                    if camera.is_connected:
                        with contextlib.suppress(Exception):
                            camera.disconnect()
                    raise CameraPreviewError(f"Could not preview camera {key}: {exc}") from exc
                capture = _Capture(camera=camera, config=config)
                self._captures[key] = capture
            capture.subscribers += 1
            return PreviewLease(self, key, capture)

    def _close(self, key: int, capture: _Capture) -> None:
        # Keep a failed close registered, so a session cannot open over it.
        try:
            capture.camera.disconnect()
        except Exception as exc:
            raise CameraPreviewError(f"Camera {key} could not be released: {exc}") from exc
        capture.closed = True
        if self._captures.get(key) is capture:
            del self._captures[key]

    def stop(self) -> None:
        with self._lock:
            for key, capture in list(self._captures.items()):
                self._close(key, capture)

    @contextlib.contextmanager
    def session_start(self) -> Iterator[None]:
        """Release idle cameras and exclude new previews until state is claimed."""
        with self._lock:
            self.stop()
            yield


def preview_config(
    index: int,
    device_id: str | None,
    width: int | None,
    height: int | None,
    fps: int | None,
    rotation: int,
    backend: str | None,
    fourcc: str | None,
):
    from lerobot.cameras.configs import Cv2Backends
    from lerobot.cameras.opencv import OpenCVCameraConfig

    from .record import _platform_backend

    return OpenCVCameraConfig(
        index_or_path=resolve_camera_index(index, device_id),
        width=width,
        height=height,
        fps=fps,
        rotation=camera_rotation(rotation),
        backend=Cv2Backends[backend] if backend else _platform_backend(),
        fourcc=fourcc,
    )
