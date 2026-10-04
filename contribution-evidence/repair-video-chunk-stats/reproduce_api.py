"""Exercise public dataset repair with repeated video filenames across chunks."""
import json
import os
import shutil
import tempfile
from pathlib import Path

cache = Path(tempfile.mkdtemp(prefix="lelab-repair-chunks-"))
os.environ["HF_LEROBOT_HOME"] = str(cache)
import numpy as np
import pyarrow.parquet as pq
from lerobot.datasets import LeRobotDataset
from fastapi.testclient import TestClient
from lelab.server import app

KEY = "observation.images.cam"
features = {
    "action": {"dtype": "float32", "shape": (2,), "names": ["a", "b"]},
    "observation.state": {"dtype": "float32", "shape": (2,), "names": ["a", "b"]},
    KEY: {"dtype": "video", "shape": (32, 32, 3), "names": ["h", "w", "c"]},
}

def record(repo_id, episodes):
    ds = LeRobotDataset.create(repo_id, fps=10, features=features, use_videos=True, video_files_size_in_mb=0)
    # One file per chunk makes the real writer exercise rollover with three episodes.
    ds.meta.info.chunks_size = 1
    ds.meta.info.video_files_size_in_mb = 0.001
    for episode in range(episodes):
        for frame in range(5):
            values = np.full(2, episode * 5 + frame, dtype=np.float32)
            ds.add_frame({"action": values, "observation.state": values, "task": "repair chunks", KEY: np.full((32, 32, 3), 30 + 180 * episode // 2, dtype=np.uint8)})
        ds.save_episode()
    ds.finalize()
    return ds.root

broken = record("repro/interrupted", 3)
reference = record("repro/reference", 2)
video_paths = sorted((broken / "videos" / KEY).rglob("*.mp4"))
assert [p.parent.name for p in video_paths] == ["chunk-000", "chunk-001", "chunk-002"]
assert all(p.name == "file-000.mp4" for p in video_paths)
shutil.rmtree(broken / "meta" / "episodes")
video_paths[-1].unlink()
with TestClient(app) as client:
    response = client.post("/dataset-info", json={"dataset_repo_id": "repro/interrupted"})
assert response.status_code == 200
api_result = response.json()
assert api_result["success"] is True
assert api_result["num_episodes"] == 2
message = "Repair triggered by POST /dataset-info"
repaired = LeRobotDataset("repro/interrupted", video_backend="pyav")
repaired_mean = json.loads((broken / "meta" / "stats.json").read_text())[KEY]["mean"]
reference_mean = json.loads((reference / "meta" / "stats.json").read_text())[KEY]["mean"]
rows = pq.read_table(broken / "meta" / "episodes" / "chunk-000" / "file-000.parquet").to_pylist()
result = {"temporary_cache": str(cache), "api_result": api_result, "message": message, "episodes": repaired.num_episodes, "frames": repaired.num_frames, "video_chunk_indices": [row[f"videos/{KEY}/chunk_index"] for row in rows], "repaired_image_mean": repaired_mean, "reference_image_mean": reference_mean, "matches_reference": bool(np.allclose(repaired_mean, reference_mean, atol=0.01)), "last_frame_image_mean": float(repaired[9][KEY].mean())}
print(json.dumps(result, indent=2))
assert result["matches_reference"], "Repair statistics decode the wrong video chunk"
