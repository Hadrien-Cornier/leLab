import type { CameraConfig } from "@/components/recording/CameraConfiguration";

export type NativePreviewCamera = Pick<CameraConfig,
  "camera_index" | "backend_device_id" | "width" | "height" | "fps" | "fourcc" | "backend" | "rotation"
>;

export function nativeCameraPreviewUrl(baseUrl: string, camera: NativePreviewCamera, retry: number): string {
  const params = new URLSearchParams({
    width: String(camera.width),
    height: String(camera.height),
    fps: String(camera.fps ?? 30),
    rotation: String(camera.rotation ?? 0),
    retry: String(retry),
  });
  if (camera.camera_index != null) params.set("index", String(camera.camera_index));
  if (camera.backend_device_id) params.set("device_id", camera.backend_device_id);
  if (camera.fourcc) params.set("fourcc", camera.fourcc);
  if (camera.backend) params.set("backend", camera.backend);
  return `${baseUrl}/camera-preview?${params}`;
}
