// @vitest-environment jsdom
import React, { act } from "react";
import { createRoot, Root } from "react-dom/client";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import NativeCameraPreview from "./NativeCameraPreview";
import { nativeCameraPreviewUrl } from "@/lib/cameraPreview";

vi.mock("@/contexts/ApiContext", () => ({ useApi: () => ({ baseUrl: "http://localhost:8000" }) }));
let root: Root;
let container: HTMLDivElement;
const camera = { camera_index: 1, backend_device_id: "native-wrist", width: 640, height: 480, fps: 30, rotation: 180 as const };

beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  container = document.createElement("div");
  root = createRoot(container);
});
afterEach(() => act(() => root.unmount()));

test("preview sends the recorder's native identity, image shape, rate, and rotation", () => {
  const url = new URL(nativeCameraPreviewUrl("http://localhost:8000", camera, 0));
  expect(Object.fromEntries(url.searchParams)).toEqual({ width: "640", height: "480", fps: "30", rotation: "180", retry: "0", index: "1", device_id: "native-wrist" });
});

test("recording handoff removes the native stream and resume creates it again", () => {
  act(() => root.render(<NativeCameraPreview camera={camera} />));
  expect(container.querySelector("img")?.getAttribute("src")).toContain("/camera-preview?");
  act(() => root.render(<NativeCameraPreview camera={camera} paused />));
  expect(container.querySelector("img")).toBeNull();
  expect(container.textContent).toContain("Preview paused");
  act(() => root.render(<NativeCameraPreview camera={camera} />));
  expect(container.querySelector("img")).not.toBeNull();
});

test("a failed native stream can be retried with a fresh URL", () => {
  act(() => root.render(<NativeCameraPreview camera={camera} />));
  act(() => container.querySelector("img")!.dispatchEvent(new Event("error")));
  expect(container.textContent).toContain("Camera preview could not start");
  act(() => container.querySelector("button")!.click());
  expect(container.querySelector("img")?.getAttribute("src")).toContain("retry=1");
});
