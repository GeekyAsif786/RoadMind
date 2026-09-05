import { Camera, Crosshair, Plus } from "lucide-react";

import { api } from "../services/api.js";
import { DIRECTIONS, WEATHER_OPTIONS, percent } from "./constants.js";

export default function DetectionPanel({
  busy,
  selectedIntersection,
  runAction,
  requireIntersection,
  detection,
  setDetection,
  detectionPreviewUrl,
  setDetectionPreviewUrl,
  correctedVehicleCount,
  setCorrectedVehicleCount,
  detectionDirection,
  setDetectionDirection,
  detectionWeather,
  setDetectionWeather,
  detectionPcuTotal,
  setDetectionPcuTotal
}) {
  return (
    <section className="control-panel">
      <div className="panel-heading">
        <Camera size={20} />
        <h2>Frame Detection</h2>
      </div>
      <label className="drop-zone">
        <input
          type="file"
          accept="image/*"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (!file) return;
            runAction(async () => {
              const previewUrl = window.URL.createObjectURL(file);
              setDetectionPreviewUrl((currentUrl) => {
                if (currentUrl) window.URL.revokeObjectURL(currentUrl);
                return previewUrl;
              });
              const result = await api.detectImage(file, selectedIntersection || undefined, false);
              setDetection(result);
              setCorrectedVehicleCount(String(result.vehicle_count));
            }, "Frame processed for review");
          }}
        />
        <Crosshair size={28} />
        <span>{detection ? `${detection.vehicle_count} vehicles detected` : "Upload frame"}</span>
      </label>
      {detectionPreviewUrl && (
        <div className="frame-preview">
          <img src={detectionPreviewUrl} alt="Uploaded traffic frame" />
        </div>
      )}
      {detection && (
        <>
          <div className="detection-strip">
            <span>{percent(detection.density)} density</span>
            <span>{detection.boxes.length} boxes</span>
          </div>
          <form
            className="correction-form"
            onSubmit={(event) => {
              event.preventDefault();
              runAction(
                () =>
                  api.createObservation({
                    intersection_id: requireIntersection(),
                    direction: detectionDirection,
                    vehicle_count: Number(correctedVehicleCount),
                    weather_condition: detectionWeather,
                    pcu_total: detectionPcuTotal ? Number(detectionPcuTotal) : null,
                    source: "human_review"
                  }),
                "Corrected frame count saved"
              );
            }}
          >
            <label>
              Corrected Count
              <input
                type="number"
                min="0"
                value={correctedVehicleCount}
                onChange={(event) => setCorrectedVehicleCount(event.target.value)}
              />
            </label>
            <label>
              Direction
              <select value={detectionDirection} onChange={(event) => setDetectionDirection(event.target.value)}>
                {DIRECTIONS.map((direction) => (
                  <option key={direction}>{direction}</option>
                ))}
              </select>
            </label>
            <label>
              Weather
              <select value={detectionWeather} onChange={(event) => setDetectionWeather(event.target.value)}>
                {WEATHER_OPTIONS.map((weather) => (
                  <option key={weather}>{weather}</option>
                ))}
              </select>
            </label>
            <label>
              PCU
              <input
                type="number"
                min="0"
                step="0.1"
                placeholder="Optional"
                value={detectionPcuTotal}
                onChange={(event) => setDetectionPcuTotal(event.target.value)}
              />
            </label>
            <button disabled={busy || !selectedIntersection}>
              <Plus size={18} />
              Save
            </button>
          </form>
        </>
      )}
    </section>
  );
}
