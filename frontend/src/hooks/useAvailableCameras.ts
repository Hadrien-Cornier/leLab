import { useCallback, useEffect, useState } from "react";
import { useApi } from "@/contexts/ApiContext";

export interface AvailableCamera {
  index: number;
  name: string;
  deviceId: string;
  backendDeviceId?: string;
  available: boolean;
}

interface UseAvailableCamerasOptions {
  /** When false, do nothing. Use to gate on modal open. */
  enabled?: boolean;
}

/**
 * Enumerates cv2 camera indices from `/available-cameras` and merges each
 * with native physical device identities. Browser IDs belong to one browser
 * and origin, so native previews do not depend on them or camera permissions.
 */
export function useAvailableCameras({
  enabled = true,
}: UseAvailableCamerasOptions = {}) {
  const { baseUrl, fetchWithHeaders } = useApi();
  const [cameras, setCameras] = useState<AvailableCamera[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const refresh = useCallback(async (): Promise<AvailableCamera[]> => {
    setIsLoading(true);
    try {
      const r = await fetchWithHeaders(`${baseUrl}/available-cameras`);
      if (!r.ok) {
        setCameras([]);
        return [];
      }
      const data = await r.json();
      const backendCams: {
        index: number;
        name?: string;
        unique_id?: string;
        available: boolean;
      }[] = data.cameras ?? [];

      const merged: AvailableCamera[] = backendCams.map((cam) => {
        const label = cam.name || `Camera ${cam.index}`;
        return {
          index: cam.index,
          name: label,
          deviceId: "",
          backendDeviceId: cam.unique_id,
          available: cam.available,
        };
      });
      setCameras(merged);
      return merged;
    } catch {
      setCameras([]);
      return [];
    } finally {
      setIsLoading(false);
    }
  }, [baseUrl, fetchWithHeaders]);

  useEffect(() => {
    if (!enabled) return;
    refresh();
    const handler = () => refresh();
    navigator.mediaDevices?.addEventListener("devicechange", handler);
    return () =>
      navigator.mediaDevices?.removeEventListener("devicechange", handler);
  }, [enabled, refresh]);

  return { cameras, isLoading, refresh };
}
