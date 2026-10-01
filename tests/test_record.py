# Copyright 2025 The HuggingFace Inc. team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Tests for lelab.record — request schemas and handler entry points."""

from __future__ import annotations

import pytest


def test_recording_request_rejects_missing_required_fields() -> None:
    from pydantic import ValidationError

    from lelab.record import RecordingRequest

    with pytest.raises(ValidationError):
        RecordingRequest()


def test_recording_status_handler_exposes_state_fields() -> None:
    from lelab.record import handle_recording_status

    result = handle_recording_status()
    assert isinstance(result, dict)
    # Pinning the exact keys so a rename in handle_recording_status surfaces here.
    assert "recording_active" in result
    assert "current_phase" in result
    assert "session_ended" in result
    assert "available_controls" in result


def test_handle_stop_recording_when_idle_returns_dict(tmp_lerobot_home) -> None:
    from lelab.record import handle_stop_recording

    result = handle_stop_recording()
    assert isinstance(result, dict)


def test_create_record_config_pins_dshow_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    """On Windows, recording must use the DSHOW backend so a camera_index opens
    the same device /available-cameras enumerated (via pygrabber, DSHOW order).
    """
    import lelab.record as record
    from lerobot.cameras.configs import Cv2Backends

    monkeypatch.setattr("platform.system", lambda: "Windows")
    monkeypatch.setattr(record, "setup_calibration_files", lambda leader, follower: ("leader", "follower"))

    request = record.RecordingRequest(
        leader_port="COM_LEADER",
        follower_port="COM_FOLLOWER",
        leader_config="leader",
        follower_config="follower",
        dataset_repo_id="user/dataset",
        single_task="pick up the cube",
        cameras={"wrist": {"type": "opencv", "camera_index": 0, "width": 640, "height": 480, "fps": 30}},
    )

    config = record.create_record_config(request)
    assert config.robot.cameras["wrist"].backend == Cv2Backends.DSHOW


def test_build_camera_configs_uses_default_backend_when_unset() -> None:
    from lelab.record import _build_camera_configs
    from lerobot.cameras.configs import Cv2Backends

    cameras = {"cam": {"type": "opencv", "camera_index": 0, "width": 640, "height": 480, "fps": 30}}
    configs = _build_camera_configs(cameras, Cv2Backends.AVFOUNDATION)

    assert configs["cam"].backend == Cv2Backends.AVFOUNDATION
    assert configs["cam"].fourcc is None
    assert configs["cam"].index_or_path == 0


def test_build_camera_configs_passes_fourcc_through() -> None:
    from lelab.record import _build_camera_configs
    from lerobot.cameras.configs import Cv2Backends

    cameras = {"cam": {"type": "opencv", "camera_index": 0, "fourcc": "MJPG"}}
    configs = _build_camera_configs(cameras, Cv2Backends.ANY)

    assert configs["cam"].fourcc == "MJPG"


@pytest.mark.parametrize(
    ("rotation", "expected"),
    [(0, 0), (90, 90), (180, 180), (270, -90)],
)
def test_build_camera_configs_rotates_only_configured_camera(rotation: int, expected: int) -> None:
    from lelab.record import _build_camera_configs
    from lerobot.cameras.configs import Cv2Backends, Cv2Rotation

    cameras = {
        "front": {"type": "opencv", "camera_index": 0},
        "wrist": {"type": "opencv", "camera_index": 1, "rotation": rotation},
    }
    configs = _build_camera_configs(cameras, Cv2Backends.ANY)

    assert configs["front"].rotation == Cv2Rotation.NO_ROTATION
    assert configs["wrist"].rotation == Cv2Rotation(expected)


@pytest.mark.parametrize("rotation", [45, -180, "180", True])
def test_build_camera_configs_rejects_invalid_rotation(rotation) -> None:
    from lelab.record import _build_camera_configs
    from lerobot.cameras.configs import Cv2Backends

    cameras = {"wrist": {"type": "opencv", "camera_index": 1, "rotation": rotation}}
    with pytest.raises(ValueError, match="camera rotation"):
        _build_camera_configs(cameras, Cv2Backends.ANY)


def test_record_camera_processes_wrist_frame_before_recording_and_preview() -> None:
    """OpenCVCamera uses this processed frame for robot observations and read_latest()."""
    import numpy as np

    from lelab.record import _build_camera_configs
    from lerobot.cameras.configs import Cv2Backends
    from lerobot.cameras.opencv import OpenCVCamera

    configs = _build_camera_configs(
        {"wrist": {"type": "opencv", "camera_index": 1, "width": 2, "height": 2, "rotation": 180}},
        Cv2Backends.ANY,
    )
    camera = OpenCVCamera(configs["wrist"])
    raw_bgr = np.array(
        [
            [[0, 0, 10], [0, 0, 20]],
            [[0, 0, 30], [0, 0, 40]],
        ],
        dtype=np.uint8,
    )

    rotated_rgb = camera._postprocess_image(raw_bgr)

    assert rotated_rgb[:, :, 0].tolist() == [[40, 30], [20, 10]]


def test_build_camera_configs_explicit_backend_overrides_default() -> None:
    from lelab.record import _build_camera_configs
    from lerobot.cameras.configs import Cv2Backends

    cameras = {"cam": {"type": "opencv", "camera_index": 0, "backend": "V4L2"}}
    configs = _build_camera_configs(cameras, Cv2Backends.AVFOUNDATION)

    assert configs["cam"].backend == Cv2Backends.V4L2


def test_build_camera_configs_invalid_backend_raises() -> None:
    from lelab.record import _build_camera_configs
    from lerobot.cameras.configs import Cv2Backends

    cameras = {"cam": {"type": "opencv", "camera_index": 0, "backend": "NOPE"}}
    with pytest.raises(KeyError):
        _build_camera_configs(cameras, Cv2Backends.ANY)


def test_build_camera_configs_skips_non_opencv_type() -> None:
    from lelab.record import _build_camera_configs
    from lerobot.cameras.configs import Cv2Backends

    cameras = {"cam": {"type": "realsense", "camera_index": 0}}
    configs = _build_camera_configs(cameras, Cv2Backends.ANY)

    assert configs == {}
