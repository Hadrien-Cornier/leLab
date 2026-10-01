export interface CameraIdentity {
  camera_index?: number;
  backend_device_id?: string;
  device_id?: string;
}

export interface DetectedCamera {
  index: number;
  backendDeviceId?: string;
  deviceId: string;
}

/** A stable backend identity takes priority over browser IDs and old indices. */
export function resolveCameraBinding<T extends DetectedCamera>(
  camera: CameraIdentity,
  available: T[],
): T | undefined {
  if (camera.backend_device_id) {
    return available.find((device) => device.backendDeviceId === camera.backend_device_id);
  }
  if (camera.device_id) {
    const browserMatch = available.find((device) => device.deviceId === camera.device_id);
    if (browserMatch) return browserMatch;
  }
  // Legacy profiles record from this exact backend index. Native previews use
  // that same index, so the preview shows the recorder's actual source.
  return available.find((device) => device.index === camera.camera_index);
}
