"""Exercise the real recording route and loop with supplied hardware devices."""
import json
import os
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

cache = Path(tempfile.mkdtemp(prefix="lelab-rotation-loop-")) if __name__ == "__main__" else Path(os.environ["HF_LEROBOT_HOME"])
os.environ["HF_LEROBOT_HOME"] = str(cache)

import av
import cv2
import draccus
import numpy as np
import yaml
from fastapi.testclient import TestClient
from lerobot.cameras.opencv import OpenCVCamera, OpenCVCameraConfig
from lerobot.teleoperators import Teleoperator
from lelab import record, rollout
from lelab.server import app
from lelab.utils import config as persistence

def main():
    raw = np.zeros((64, 96, 3), dtype=np.uint8)
    raw[:32, :48] = [230, 30, 30]
    raw[:32, 48:] = [30, 230, 30]
    raw[32:, :48] = [30, 30, 230]
    raw[32:, 48:] = [230, 230, 30]
    cv2.putText(raw, "TOP", (5, 21), cv2.FONT_HERSHEY_SIMPLEX, .45, (255, 255, 255), 1)
    source = cv2.cvtColor(raw, cv2.COLOR_RGB2BGR)
    output = []
    observations = {}
    captures = []

    class SuppliedCapture:
        def __init__(self, index, backend):
            self.index = index
            self.open = True
            self.settings = {cv2.CAP_PROP_FRAME_WIDTH: 96., cv2.CAP_PROP_FRAME_HEIGHT: 64., cv2.CAP_PROP_FPS: 10.}
            captures.append(self)
        def isOpened(self): return self.open
        def get(self, key): return self.settings.get(key, 0.)
        def set(self, key, value):
            # A real fixed source must reject a swapped sensor-resolution request.
            if key in (cv2.CAP_PROP_FRAME_WIDTH, cv2.CAP_PROP_FRAME_HEIGHT):
                return self.settings[key] == value
            self.settings[key] = value
            return True
        def read(self):
            time.sleep(.02)
            return self.open, source.copy()
        def release(self): self.open = False

    def make_robot(cfg):
        cameras = {name: OpenCVCamera(camera_cfg) for name, camera_cfg in cfg.cameras.items()}
        state = {"count": 0}
        def observe():
            values = {name: camera.async_read(timeout_ms=2000) for name, camera in cameras.items()}
            observations.update(values)
            state["count"] += 1
            if state["count"] >= 5:
                record.recording_events["_exit_early_triggered"] = True
                record.recording_events["exit_early"] = True
            return {"joint.pos": 0., **values}
        def disconnect():
            for camera in cameras.values():
                if camera.is_connected: camera.disconnect()
        return SimpleNamespace(name="so101_follower", cameras=cameras, calibration={}, bus=MagicMock(),
                               action_features={"joint.pos": float},
                               observation_features={"joint.pos": float, **{name: (cam.height, cam.width, 3) for name, cam in cameras.items()}},
                               configure=lambda: None, get_observation=observe, send_action=lambda action: action,
                               disconnect=disconnect, is_connected=True)

    def make_teleop(cfg):
        teleop = MagicMock(spec=Teleoperator)
        teleop.bus = MagicMock()
        teleop.calibration = {}
        teleop.get_action.return_value = {"joint.pos": 0.}
        return teleop

    original_create = record.create_record_config
    def quiet_create(request):
        cfg = original_create(request)
        cfg.play_sounds = False
        cfg.dataset.streaming_encoding = False
        return cfg

    with patch.object(persistence, "ROBOTS_PATH", str(cache / "robots")), \
         patch.object(record, "setup_calibration_files", return_value=("supplied", "supplied")), \
         patch.object(record, "create_record_config", side_effect=quiet_create), \
         patch("lerobot.robots.make_robot_from_config", side_effect=make_robot), \
         patch("lerobot.teleoperators.make_teleoperator_from_config", side_effect=make_teleop), \
         patch("cv2.VideoCapture", SuppliedCapture):
        client = TestClient(app)
        for rotation in (0, 90, 180, 270):
            camera = {"id": "wrist", "name": "wrist", "device_id": "supplied-wrist",
                      "type": "opencv", "camera_index": 1, "width": 96, "height": 64,
                      "fps": 10, "rotation": rotation}
            profile = {"cameras": [camera]}
            client.post(f"/robots/repro_{rotation}?create=true", json=profile).raise_for_status()
            saved = client.get(f"/robots/repro_{rotation}").json()["robot"]["cameras"][0]
            assert saved["rotation"] == rotation
            cameras = {"front": {**camera, "camera_index": 0, "rotation": 0}, "wrist": saved}
            # The user-facing camera request omits profile-only UI fields.
            cameras = {name: {k: v for k, v in cam.items() if k not in ("id", "name", "device_id")} for name, cam in cameras.items()}
            payload = {"leader_port": "supplied", "follower_port": "supplied", "leader_config": "supplied",
                       "follower_config": "supplied", "dataset_repo_id": f"repro/rotation_{rotation}",
                       "single_task": "rotate a supplied source", "num_episodes": 1, "episode_time_s": 2,
                       "reset_time_s": 0, "fps": 10, "cameras": cameras}
            response = client.post("/start-recording", json=payload)
            assert response.status_code == 200 and response.json()["success"], response.text
            record.recording_thread.join(timeout=30)
            assert not record.recording_thread.is_alive(), "Recording did not terminate"
            assert record.last_recording_info["success"], record.last_recording_info
            root = cache / response.json()["dataset_id"]
            expected = raw if rotation == 0 else cv2.rotate(raw, {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}[rotation])
            for name, reference in (("front", raw), ("wrist", expected)):
                video = next(root.glob(f"videos/observation.images.{name}/**/*.mp4"))
                with av.open(str(video)) as container:
                    image = next(container.decode(video=0)).to_ndarray(format="rgb24")
                assert image.shape == reference.shape, (rotation, name, image.shape, reference.shape)
                error = float(np.abs(image.astype(float) - reference).mean())
                assert error < 10, (rotation, name, error)
                assert np.array_equal(observations[name], reference), (rotation, name, "observation")
            # Parse the actual rollout camera argument, then process the policy's raw input.
            cli = rollout._format_cameras_arg(cameras)
            camera_data = yaml.safe_load(cli)["wrist"]
            policy_camera = OpenCVCamera(draccus.decode(OpenCVCameraConfig, {k: v for k, v in camera_data.items() if k != "type"}))
            policy_input = policy_camera._postprocess_image(source)
            assert np.array_equal(policy_input, expected)
            output.append({"rotation": rotation, "frames": record.last_recording_info["total_frames"],
                           "shape": list(expected.shape), "profile_reload": True, "front_unchanged": True,
                           "recording_loop": True, "saved_video_mean_error": error,
                           "policy_camera_input_exact": True, "capture_settings": captures[-1].settings,
                           "dataset": str(root)})
    print("RESULT " + json.dumps({"runs": output, "hardware": "supplied capture and motor devices; no physical hardware", "cache": str(cache)}, sort_keys=True))


if __name__ == "__main__":
    main()
