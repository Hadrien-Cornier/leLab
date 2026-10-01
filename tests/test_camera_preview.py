"""Camera identity, preview ownership, and session handoff checks."""

import asyncio
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from lelab import camera_preview as preview


@dataclass
class Config:
    index_or_path: int = 0
    rotation: int = 0


@pytest.fixture
def cameras():
    created = []

    def factory(config):
        camera = MagicMock()
        camera.config = config
        camera.is_connected = True
        camera.read_latest.return_value = np.full((3, 4, 3), [200, 10, 20], dtype=np.uint8)
        created.append(camera)
        return camera

    return created, factory


def test_identical_camera_names_resolve_by_native_identity(monkeypatch):
    monkeypatch.setattr(
        preview,
        "_device_provider",
        lambda: [
            {"index": 0, "name": "icspring", "unique_id": "wrist"},
            {"index": 1, "name": "icspring", "unique_id": "front"},
        ],
    )
    assert preview.resolve_camera_index(0, "front") == 1
    assert preview.resolve_camera_index(1, "wrist") == 0
    with pytest.raises(preview.CameraPreviewError, match="disconnected"):
        preview.resolve_camera_index(0, "unplugged")
    assert preview.resolve_camera_index(0) == 0


def test_multiple_tabs_share_one_camera_and_last_disconnect_releases(cameras):
    created, factory = cameras
    manager = preview.CameraPreviewManager(camera_factory=factory)
    first = manager.acquire(Config())
    second = manager.acquire(Config())
    assert len(created) == 1
    assert first.jpeg().startswith(b"\xff\xd8")
    first.release()
    created[0].disconnect.assert_not_called()
    second.release()
    second.release()
    created[0].disconnect.assert_called_once()
    assert not manager._captures


def test_new_rotation_closes_old_capture_without_old_tab_closing_new(cameras):
    created, factory = cameras
    manager = preview.CameraPreviewManager(camera_factory=factory)
    old = manager.acquire(Config(rotation=0))
    new = manager.acquire(Config(rotation=180))
    created[0].disconnect.assert_called_once()
    assert old.jpeg() is None
    old.release()
    created[1].disconnect.assert_not_called()
    new.release()
    created[1].disconnect.assert_called_once()


def test_start_hands_off_camera_and_active_session_blocks_reopening(cameras):
    created, factory = cameras
    active = False
    manager = preview.CameraPreviewManager(busy=lambda: active, camera_factory=factory)
    lease = manager.acquire(Config())
    with manager.session_start():
        created[0].disconnect.assert_called_once()
        active = True
    assert lease.jpeg() is None
    with pytest.raises(preview.CameraPreviewError, match="session owns"):
        manager.acquire(Config())
    assert len(created) == 1


def test_failed_release_prevents_session_from_opening_camera(cameras):
    created, factory = cameras
    manager = preview.CameraPreviewManager(camera_factory=factory)
    manager.acquire(Config())
    created[0].disconnect.side_effect = RuntimeError("driver still owns device")
    opened_session = False
    with pytest.raises(preview.CameraPreviewError, match="could not be released"), manager.session_start():
        opened_session = True
    assert not opened_session
    assert manager._captures


def test_failed_first_frame_cleans_up_camera(cameras):
    created, factory = cameras

    def no_frames(config):
        camera = factory(config)
        camera.read_latest.side_effect = TimeoutError("no frames")
        return camera

    manager = preview.CameraPreviewManager(camera_factory=no_frames)
    with pytest.raises(preview.CameraPreviewError, match="no frames"):
        manager.acquire(Config())
    created[0].disconnect.assert_called_once()
    assert not manager._captures


def test_recording_and_inference_resolve_native_source_and_strip_ui_fields(monkeypatch):
    from lelab.record import _build_camera_configs
    from lelab.rollout import _format_cameras_arg
    from lerobot.cameras.configs import Cv2Backends

    monkeypatch.setattr(preview, "_device_provider", lambda: [{"index": 2, "unique_id": "wrist"}])
    configs = {
        "wrist": {
            "type": "opencv",
            "camera_index": 1,
            "backend_device_id": "wrist",
            "device_name": "icspring",
            "device_id": "browser-hash",
            "width": 640,
            "height": 480,
            "fps": 30,
            "rotation": 180,
        }
    }
    camera = _build_camera_configs(configs, Cv2Backends.AVFOUNDATION)["wrist"]
    assert camera.index_or_path == 2
    assert camera.rotation.value == 180
    arg = _format_cameras_arg(configs)
    assert "index_or_path: 2" in arg
    assert "rotation: 180" in arg
    assert "device_id" not in arg
    assert "device_name" not in arg
    assert configs["wrist"]["camera_index"] == 1


def test_mjpeg_disconnect_releases_capture(monkeypatch, cameras):
    from lelab import server

    created, factory = cameras
    manager = preview.CameraPreviewManager(camera_factory=factory)
    monkeypatch.setattr(server, "camera_previews", manager)
    request = MagicMock()
    request.is_disconnected = AsyncMock(side_effect=[False, True])
    request.headers = {}
    response = server.camera_preview(request, index=0, width=640, height=480, fps=30)

    async def consume():
        chunks = [chunk async for chunk in response.body_iterator]
        await response.background()
        return chunks

    chunks = asyncio.run(consume())
    assert len(chunks) == 1
    assert chunks[0].startswith(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n\xff\xd8")
    created[0].disconnect.assert_called_once()
    assert not manager._captures


def test_api_rejects_preview_during_recording(client, monkeypatch):
    from lelab import server

    monkeypatch.setattr(server._record, "recording_active", True)
    response = client.get("/camera-preview?index=0")
    assert response.status_code == 409
    assert "session owns" in response.json()["detail"]


def test_api_rejects_invalid_rotation_and_disconnected_identity(client, monkeypatch):
    assert client.get("/camera-preview?index=0&rotation=45").status_code == 422
    monkeypatch.setattr(preview, "_device_provider", lambda: [])
    response = client.get("/camera-preview?index=0&device_id=disconnected")
    assert response.status_code == 422


def test_recording_route_releases_preview_before_start(client, monkeypatch, cameras):
    from lelab import server

    created, factory = cameras
    manager = preview.CameraPreviewManager(camera_factory=factory)
    manager.acquire(Config())
    monkeypatch.setattr(server, "camera_previews", manager)

    def start(request):
        created[0].disconnect.assert_called_once()
        assert not manager._captures
        return {"success": True}

    monkeypatch.setattr(server, "handle_start_recording", start)
    response = client.post(
        "/start-recording",
        json={
            "leader_port": "leader",
            "follower_port": "follower",
            "leader_config": "leader",
            "follower_config": "follower",
            "dataset_repo_id": "test/cleanup",
            "single_task": "put objects in bin",
        },
    )
    assert response.json() == {"success": True}


@pytest.mark.parametrize(
    "headers",
    [
        {"origin": "https://other-site.example"},
        {"referer": "https://other-site.example/gallery"},
        {"origin": "http://localhost:9999"},
        {"origin": "null"},
        {"sec-fetch-site": "cross-site"},
    ],
)
def test_foreign_page_cannot_open_or_stop_previews(client, monkeypatch, headers):
    from lelab import server

    acquire = MagicMock()
    stop = MagicMock()
    monkeypatch.setattr(server.camera_previews, "acquire", acquire)
    monkeypatch.setattr(server.camera_previews, "stop", stop)
    assert client.get("/camera-preview?index=0", headers=headers).status_code == 403
    assert client.post("/camera-preview/stop", headers=headers).status_code == 403
    acquire.assert_not_called()
    stop.assert_not_called()


@pytest.mark.parametrize(
    "headers",
    [
        {"origin": "http://127.0.0.1:8000"},
        {"referer": "http://localhost:8000/recording"},
        {"origin": "http://localhost:8080", "sec-fetch-site": "cross-site"},
        {},
    ],
)
def test_local_ui_and_cli_can_stop_previews(client, headers):
    assert client.post("/camera-preview/stop", headers=headers).status_code == 200
