import { useEffect, useState } from "react";
import { VideoOff } from "lucide-react";
import { useApi } from "@/contexts/ApiContext";
import { NativePreviewCamera, nativeCameraPreviewUrl } from "@/lib/cameraPreview";

/** Native frames come from the same OpenCV source the recorder will open. */
export default function NativeCameraPreview({
  camera,
  paused = false,
  className = "w-full h-full",
}: {
  camera: NativePreviewCamera;
  paused?: boolean;
  className?: string;
}) {
  const { baseUrl } = useApi();
  const [failed, setFailed] = useState(false);
  const [retry, setRetry] = useState(0);
  const source = nativeCameraPreviewUrl(baseUrl, camera, retry);
  const selected = camera.camera_index != null || !!camera.backend_device_id;
  useEffect(() => setFailed(false), [source, paused]);

  if (paused || !selected || failed) {
    return (
      <div className={`${className} flex flex-col items-center justify-center bg-gray-800`}>
        <VideoOff className="w-6 h-6 text-gray-500 mb-2" />
        <span className="text-gray-400 text-sm text-center px-3">
          {paused ? "Preview paused" : !selected ? "Choose a camera in Calibration." :
            "Camera preview could not start. Close other camera apps or reconnect the camera."}
        </span>
        {!paused && selected && <button type="button" onClick={() => setRetry((value) => value + 1)} className="mt-2 text-sm text-blue-400">Retry preview</button>}
      </div>
    );
  }

  return <img
    key={source}
    src={source}
    alt="Live camera preview"
    className={`${className} object-cover bg-black`}
    onError={() => setFailed(true)}
  />;
}
