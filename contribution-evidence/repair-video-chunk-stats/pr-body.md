Opening an interrupted local recording can rebuild its episode index and image statistics. When the retained videos span chunks, each chunk can contain `file-000.mp4`. The repair currently selects the first matching file name across all chunks, so image normalization statistics can describe the wrong episode.

Resolve each video's path from both its chunk index and file index. The regression records three synthetic episodes through LeRobot's writer, removes the final video and episode index, then checks the retained images and every statistical field against a two-episode reference.

Validation:

- The real `POST /dataset-info` endpoint reproduces the failure on upstream `454b19f` and passes after the fix.
- The reproduction changes the repaired image mean from 0.462745 to 0.286275. The source-pixel reference is 0.294118; the remaining difference is within the stated lossy AV1 tolerance.
- All 271 Python tests pass. All pre-commit checks pass.
- An independent agent reviewed the path contract and regression test.

Prepared with Codex. Validation uses temporary synthetic datasets.
