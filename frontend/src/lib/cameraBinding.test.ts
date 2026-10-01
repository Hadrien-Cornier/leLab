import { expect, test } from "vitest";
import { resolveCameraBinding } from "./cameraBinding";

const devices = [
  { index: 0, backendDeviceId: "native-wrist", deviceId: "", name: "USB camera" },
  { index: 1, backendDeviceId: "native-front", deviceId: "", name: "USB camera" },
];

test("a physical camera follows its identity when identical-name cameras change index", () => {
  expect(resolveCameraBinding({ camera_index: 0, backend_device_id: "native-front", device_id: "old-browser-id" }, devices)?.index).toBe(1);
});

test("a removed physical camera never binds to a replacement at the old index", () => {
  expect(resolveCameraBinding({ camera_index: 0, backend_device_id: "unplugged-camera" }, devices)).toBeUndefined();
});

test("a legacy profile previews the exact native index used by its recorder", () => {
  expect(resolveCameraBinding({ camera_index: 1, device_id: "another-browser-id" }, devices)?.backendDeviceId).toBe("native-front");
});
