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

"""Translate UI camera orientation to LeRobot's OpenCV rotation enum."""

from lerobot.cameras.configs import Cv2Rotation


def camera_rotation(value: int | None) -> Cv2Rotation:
    """Accept the UI's clockwise 0/90/180/270 degrees.

    LeRobot represents 270 degrees clockwise as -90 degrees. Reject values
    outside the supported quarter-turns instead of silently recording frames
    with the wrong orientation.
    """
    if value is None:
        return Cv2Rotation.NO_ROTATION
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"camera rotation must be an integer degree value, got {value!r}")
    if value == 270:
        return Cv2Rotation.ROTATE_270
    if value not in (0, 90, 180):
        raise ValueError(f"camera rotation must be 0, 90, 180, or 270 degrees, got {value}")
    return Cv2Rotation(value)
