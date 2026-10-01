import React, { useState } from "react";
import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { useRobots } from "@/hooks/useRobots";
import CameraFeed from "./CameraFeed";
import { useAvailableCameras } from "@/hooks/useAvailableCameras";
import { resolveCameraBinding } from "@/lib/cameraBinding";

/**
 * Optional live camera panel for the teleoperation page. Off by default so we
 * camera captures start only after enabling the panel.
 *
 * A strict mirror of the selected robot's configured cameras: one live feed per
 * camera on the robot record (e.g. "wrist_cam", "webcam"), stacked vertically.
 * If the robot has none configured it shows nothing — teleop never surfaces a
 * device that wasn't deliberately added to the robot.
 */
const TeleopCameraPanel: React.FC = () => {
  const [enabled, setEnabled] = useState(false);
  // A fresh stream request after reconnecting a camera.
  const [reloadKey, setReloadKey] = useState(0);
  const { selectedRecord, isLoading: robotsLoading } = useRobots();
  const { cameras: availableCameras, refresh } = useAvailableCameras({ enabled });

  // Show exactly the configured native recording sources.
  const configured = selectedRecord?.cameras ?? [];
  const feeds = configured.map((c) => ({
    key: c.id,
    name: c.name,
    deviceId: c.device_id,
    rotation: c.rotation ?? 0,
    camera: {
      ...c,
      camera_index: resolveCameraBinding(c, availableCameras)?.index ?? c.camera_index,
    },
  }));

  return (
    <div className="bg-gray-900 rounded-lg p-4 flex flex-col gap-4 h-full">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-medium text-gray-200">Cameras</h2>
        <div className="flex items-center gap-2">
          {enabled && feeds.length > 0 && (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              onClick={() => { void refresh(); setReloadKey((k) => k + 1); }}
              className="h-9 w-9 text-gray-400 hover:text-white flex-shrink-0"
              title="Retry camera feeds (e.g. after reconnecting a camera)"
              aria-label="Retry camera feeds"
            >
              <RefreshCw className="w-4 h-4" />
            </Button>
          )}
          <Label htmlFor="teleop-camera-toggle" className="text-sm text-gray-400">
            {enabled ? "On" : "Off"}
          </Label>
          <Switch
            id="teleop-camera-toggle"
            checked={enabled}
            onCheckedChange={setEnabled}
          />
        </div>
      </div>

      {enabled ? (
        feeds.length > 0 ? (
          <div className="flex flex-col gap-3 overflow-y-auto">
            {feeds.map((feed) => (
              <CameraFeed
                key={`${feed.key}:${reloadKey}`}
                deviceId={feed.deviceId}
                label={feed.name}
                rotation={feed.rotation}
                camera={feed.camera}
              />
            ))}
          </div>
        ) : (
          <p className="text-sm text-gray-500">
            {robotsLoading
              ? "Loading robot..."
              : "No cameras configured for this robot. Add them during calibration to see live feeds here."}
          </p>
        )
      ) : (
        <p className="text-sm text-gray-500">
          Turn on to watch your cameras while you teleoperate.
        </p>
      )}
    </div>
  );
};

export default TeleopCameraPanel;
