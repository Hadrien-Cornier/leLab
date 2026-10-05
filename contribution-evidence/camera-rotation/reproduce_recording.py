"""Run the recording API with real camera processing and a temporary dataset.

Only the hardware capture and robot producer are supplied. No camera or motor
opens. The request, camera config, camera processing, writer and video decoder
are the production implementations.
"""
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

cache = Path(tempfile.mkdtemp(prefix="lelab-rotation-"))
os.environ["HF_LEROBOT_HOME"] = str(cache)

import av
import cv2
import numpy as np
from fastapi.testclient import TestClient
from lerobot.cameras.opencv import OpenCVCamera
from lerobot.datasets import LeRobotDataset
from lelab import record
from lelab.server import app

upright = np.zeros((48, 64, 3), dtype=np.uint8)
upright[:24, :32] = [230, 30, 30]
upright[:24, 32:] = [30, 230, 30]
upright[24:, :32] = [30, 30, 230]
upright[24:, 32:] = [230, 230, 30]
raw_rgb = cv2.rotate(upright, cv2.ROTATE_180)
results = {}

def supplied_robot_producer(cfg, events):
    frames = {}
    features = {
        "action": {"dtype": "float32", "shape": (1,), "names": ["joint"]},
        "observation.state": {"dtype": "float32", "shape": (1,), "names": ["joint"]},
    }
    for name, camera_cfg in cfg.robot.cameras.items():
        camera = OpenCVCamera(camera_cfg)
        # This is the real camera driver's transform and dimensional validation.
        frame = camera._postprocess_image(cv2.cvtColor(raw_rgb, cv2.COLOR_RGB2BGR))
        frames[name] = frame
        features[f"observation.images.{name}"] = {
            "dtype": "video", "shape": frame.shape, "names": ["height", "width", "channels"]
        }
        results[name] = {"rotation": int(camera_cfg.rotation), "shape": list(frame.shape)}
    dataset = LeRobotDataset.create(cfg.dataset.repo_id, fps=10, features=features,
                                   use_videos=True, streaming_encoding=False)
    for _ in range(5):
        dataset.add_frame({"action": np.zeros(1, dtype=np.float32),
                           "observation.state": np.zeros(1, dtype=np.float32),
                           "task": "rotation reproduction",
                           **{f"observation.images.{name}": frame for name, frame in frames.items()}})
    dataset.save_episode()
    dataset.finalize()
    results["root"] = str(dataset.root)
    return dataset

payload = {"leader_port": "supplied", "follower_port": "supplied",
           "leader_config": "supplied", "follower_config": "supplied",
           "dataset_repo_id": "repro/camera_rotation", "single_task": "rotation reproduction",
           "num_episodes": 1, "episode_time_s": 1, "reset_time_s": 0,
           "push_to_hub": False,
           "cameras": {"wrist": {"type": "opencv", "camera_index": 0,
                                 "width": 64, "height": 48, "fps": 10, "rotation": 180}}}
with patch.object(record, "setup_calibration_files", return_value=("supplied", "supplied")), \
     patch.object(record, "record_with_web_events", side_effect=supplied_robot_producer):
    # No startup hooks are needed to exercise this HTTP route.
    client = TestClient(app)
    response = client.post("/start-recording", json=payload)
    results["http"] = response.json()
    assert response.status_code == 200 and results["http"]["success"]
    record.recording_thread.join(timeout=30)
    assert not record.recording_thread.is_alive()
    assert record.last_recording_info["success"], record.last_recording_info
video = next(Path(results["root"]).glob("videos/observation.images.wrist/**/*.mp4"))
with av.open(str(video)) as container:
    decoded = next(container.decode(video=0)).to_ndarray(format="rgb24")
results["video"] = str(video)
results["mean_absolute_error_upright"] = float(np.abs(decoded.astype(float) - upright).mean())
results["upright"] = results["mean_absolute_error_upright"] < 10
print("RESULT " + json.dumps(results, sort_keys=True))
if not results["upright"]:
    raise SystemExit("Reproduced: recording drops requested wrist rotation")
