import React from "react";
import { VideoOff } from "lucide-react";
import { useCameraStream } from "@/hooks/useCameraStream";
import NativeCameraPreview from "./NativeCameraPreview";
import type { NativePreviewCamera } from "@/lib/cameraPreview";

interface CameraFeedProps {
  /** Browser deviceId to stream. Empty string renders the "no camera" state. */
  deviceId: string;
  /** Optional caption shown under the feed. */
  label?: string;
  rotation?: 0 | 180;
  camera?: NativePreviewCamera;
}

/** Live browser-camera feed bound to a deviceId via getUserMedia. */
const CameraFeed: React.FC<CameraFeedProps> = ({ deviceId, label, rotation = 0, camera }) => {
  const { videoRef, hasError, errorMessage, retry } = useCameraStream(deviceId, !!camera);
  const showVideo = deviceId && !hasError;

  return (
    <div className="bg-gray-900 rounded-lg border border-gray-700 overflow-hidden">
      <div className="aspect-[4/3] bg-gray-800 relative">
        {camera ? <NativeCameraPreview camera={camera} /> : showVideo ? (
          <video
            ref={videoRef}
            autoPlay
            muted
            playsInline
            className="w-full h-full object-cover"
            style={{ transform: `rotate(${rotation}deg)` }}
          />
        ) : (
          <div className="w-full h-full flex flex-col items-center justify-center">
            <VideoOff className="w-8 h-8 text-gray-500 mb-2" />
            <span className="text-gray-400 text-sm text-center px-3">
              {deviceId ? errorMessage ?? "Preview failed" : "No camera selected"}
            </span>
            {deviceId && <button type="button" onClick={retry} className="mt-2 text-sm text-blue-400">Retry preview</button>}
          </div>
        )}
      </div>
      {label && (
        <div className="p-2 text-sm text-gray-300 truncate border-t border-gray-800">
          {label}
        </div>
      )}
    </div>
  );
};

export default CameraFeed;
