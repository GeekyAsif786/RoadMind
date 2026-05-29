import {
  Activity,
  Ambulance,
  BrainCircuit,
  Camera,
  Calculator,
  ChevronDown,
  ChevronUp,
  CircleGauge,
  Crosshair,
  GitBranch,
  KeyRound,
  MapPin,
  Play,
  Plus,
  Radar,
  RotateCcw,
  Route,
  RadioTower,
  RefreshCw,
  ShieldAlert,
  TrafficCone,
  Zap
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import MetricCard from "./components/MetricCard.jsx";
import { api } from "./services/api.js";

const SELECTED_INTERSECTION_KEY = "traffic-manager:selected-intersection";
const DIRECTIONS = ["ALL", "N", "S", "E", "W", "NE", "NW", "SE", "SW"];
const WEATHER_OPTIONS = ["clear", "light_rain", "heavy_rain", "fog", "smog"];
const ROAD_TYPE_OPTIONS = [
  { value: "urban", label: "Urban arterial" },
  { value: "highway", label: "Highway / expressway" },
  { value: "service", label: "Service road" }
];
const DAY_OF_WEEK_OPTIONS = [
  { value: 0, label: "Monday" },
  { value: 1, label: "Tuesday" },
  { value: 2, label: "Wednesday" },
  { value: 3, label: "Thursday" },
  { value: 4, label: "Friday" },
  { value: 5, label: "Saturday" },
  { value: 6, label: "Sunday" }
];
const PCU_QUANTITY_SLIDER_MAX = 100;
const PCU_CALCULATOR_DEFAULT_POSITION = { right: 24, bottom: 24 };
const TRAINING_POLL_INTERVAL_MS = 1500;
const TRAINING_MAX_POLLS = 80;
const PCU_VEHICLE_OPTIONS = [
  { key: "two_wheeler", label: "Two-wheeler", factor: 0.5 },
  { key: "auto_rickshaw", label: "Auto rickshaw", factor: 0.8 },
  { key: "car", label: "Car", factor: 1.0 },
  { key: "taxi", label: "Taxi", factor: 1.0 },
  { key: "mini_bus", label: "Mini bus", factor: 2.0 },
  { key: "bus", label: "Bus", factor: 3.0 },
  { key: "truck", label: "Truck", factor: 3.5 },
  { key: "tractor", label: "Tractor", factor: 4.0 },
  { key: "cattle", label: "Cattle", factor: 1.5 },
  { key: "cycle", label: "Cycle", factor: 0.3 },
  { key: "e_rickshaw", label: "E-rickshaw", factor: 0.6 },
  { key: "unknown", label: "Unknown", factor: 1.0 }
];

const emptySummary = {
  intersections: 0,
  active_emergencies: 0,
  latest_density: null,
  latest_vehicle_count: null,
  signal_plans: [],
  observations: [],
  emergencies: [],
  predictions: [],
  metadata: {}
};

function percent(value) {
  if (value === null || value === undefined) return "0%";
  return `${Math.round(value * 100)}%`;
}

function createEmptyPcuCounts() {
  return PCU_VEHICLE_OPTIONS.reduce((counts, vehicle) => ({ ...counts, [vehicle.key]: 0 }), {});
}

function normalizePcuQuantity(value) {
  const parsedValue = Number(value);
  if (!Number.isFinite(parsedValue) || parsedValue < 0) return 0;
  return Math.floor(parsedValue);
}

function formatPcuTotal(value) {
  if (Number.isInteger(value)) return String(value);
  return value.toFixed(2).replace(/\.?0+$/, "");
}

function calculatePcuTotals(counts) {
  return PCU_VEHICLE_OPTIONS.reduce(
    (totals, vehicle) => {
      const quantity = normalizePcuQuantity(counts[vehicle.key]);
      return {
        vehicleCount: totals.vehicleCount + quantity,
        pcuTotal: totals.pcuTotal + quantity * vehicle.factor
      };
    },
    { vehicleCount: 0, pcuTotal: 0 }
  );
}

export default function App() {
  const [summary, setSummary] = useState(emptySummary);
  const [intersections, setIntersections] = useState([]);
  const [selectedIntersection, setSelectedIntersection] = useState(
    () => window.localStorage.getItem(SELECTED_INTERSECTION_KEY) ?? ""
  );
  const [status, setStatus] = useState("Connecting");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState(null);
  const [detection, setDetection] = useState(null);
  const [detectionPreviewUrl, setDetectionPreviewUrl] = useState("");
  const [correctedVehicleCount, setCorrectedVehicleCount] = useState("");
  const [detectionDirection, setDetectionDirection] = useState("ALL");
  const [detectionWeather, setDetectionWeather] = useState("clear");
  const [detectionPcuTotal, setDetectionPcuTotal] = useState("");
  const [lastPredictions, setLastPredictions] = useState({});
  const [apiKey, setApiKey] = useState(() => window.localStorage.getItem(api.apiKeyStorageKey) ?? "");
  const [predictionDirection, setPredictionDirection] = useState("ALL");
  const [predictionWeather, setPredictionWeather] = useState("clear");
  const [predictionPcuTotal, setPredictionPcuTotal] = useState("");
  const [predictionHourOfDay, setPredictionHourOfDay] = useState("");
  const [predictionDayOfWeek, setPredictionDayOfWeek] = useState("");
  const [manualVehicleCount, setManualVehicleCount] = useState(24);
  const [manualPcuTotal, setManualPcuTotal] = useState("");
  const [manualAvgSpeed, setManualAvgSpeed] = useState("");

  const latestPlan = summary.signal_plans?.[0];
  const activeEmergencies = useMemo(
    () => summary.emergencies.filter((event) => event.status === "active"),
    [summary.emergencies]
  );

  async function refresh(intersectionId = selectedIntersection) {
    try {
      const [summaryPayload, intersectionsPayload] = await Promise.all([
        api.summary(intersectionId),
        api.intersections()
      ]);
      setSummary(summaryPayload);
      setIntersections(intersectionsPayload);
      if (!intersectionId && intersectionsPayload[0]) {
        setSelectedIntersection(intersectionsPayload[0].id);
        window.localStorage.setItem(SELECTED_INTERSECTION_KEY, intersectionsPayload[0].id);
      }
      setStatus("Live");
    } catch (error) {
      setStatus("Offline");
      setNotice({ type: "error", message: error.message });
    }
  }

  useEffect(() => {
    refresh(selectedIntersection);
    const timer = window.setInterval(() => refresh(selectedIntersection), 15000);
    return () => window.clearInterval(timer);
  }, [selectedIntersection]);

  useEffect(() => {
    return () => {
      if (detectionPreviewUrl) {
        window.URL.revokeObjectURL(detectionPreviewUrl);
      }
    };
  }, [detectionPreviewUrl]);

  async function runAction(action, success) {
    setBusy(true);
    setNotice(null);
    try {
      await action();
      setNotice({ type: "success", message: success });
      await refresh();
    } catch (error) {
      setNotice({ type: "error", message: error.message });
    } finally {
      setBusy(false);
    }
  }

  async function trainPredictionModel() {
    const queued = await api.trainPrediction();
    if (!queued.job_id) {
      return queued;
    }

    setNotice({ type: "success", message: "Model training queued" });
    for (let attempt = 0; attempt < TRAINING_MAX_POLLS; attempt += 1) {
      await new Promise((resolve) => window.setTimeout(resolve, TRAINING_POLL_INTERVAL_MS));
      const job = await api.jobStatus(queued.job_id);
      if (job.status === "finished") {
        return job.result ?? queued;
      }
      if (job.status === "failed" || job.status === "not_found") {
        throw new Error(job.error || "Model training failed");
      }
    }

    throw new Error("Model training did not finish before the status check timed out");
  }

  function requireIntersection() {
    if (!selectedIntersection) throw new Error("Create or select an intersection first");
    return selectedIntersection;
  }

  return (
    <main className="app-shell">
      <section className="topbar">
        <div>
          <span className={`live-dot ${status.toLowerCase()}`} />
          <span>{status}</span>
          <h1>Smart Traffic Optimization</h1>
        </div>
        <div className="topbar-actions">
          <div className="api-key-field">
            <KeyRound size={16} />
            <input
              type="password"
              placeholder="API key"
              value={apiKey}
              onChange={(event) => {
                setApiKey(event.target.value);
                if (event.target.value) {
                  window.localStorage.setItem(api.apiKeyStorageKey, event.target.value);
                } else {
                  window.localStorage.removeItem(api.apiKeyStorageKey);
                }
              }}
            />
          </div>
          <select
            value={selectedIntersection}
            onChange={(event) => {
              setSelectedIntersection(event.target.value);
              if (event.target.value) {
                window.localStorage.setItem(SELECTED_INTERSECTION_KEY, event.target.value);
              } else {
                window.localStorage.removeItem(SELECTED_INTERSECTION_KEY);
              }
            }}
          >
            <option value="">Intersection</option>
            {intersections.map((intersection) => (
              <option key={intersection.id} value={intersection.id}>
                {intersection.name}
              </option>
            ))}
          </select>
          <button
            className="icon-button"
            onClick={() => runAction(async () => {}, "Dashboard refreshed")}
            title="Refresh"
            aria-label="Refresh"
          >
            <RefreshCw size={18} />
          </button>
        </div>
      </section>

      {notice && <div className={`notice ${notice.type}`}>{notice.message}</div>}

      <section className="metrics-grid">
        <MetricCard icon={MapPin} label="Intersections" value={summary.intersections} tone="green" />
        <MetricCard icon={CircleGauge} label="Current Density" value={percent(summary.latest_density)} tone="amber" />
        <MetricCard icon={TrafficCone} label="Vehicle Count" value={summary.latest_vehicle_count ?? 0} tone="blue" />
        <MetricCard icon={Ambulance} label="Emergencies" value={summary.active_emergencies} tone="red" />
      </section>

      <section className="operations-grid">
        <section className="control-panel">
          <div className="panel-heading">
            <RadioTower size={20} />
            <h2>Signal Control</h2>
          </div>
          <div className="signal-stage">
            <div className="signal-light red" />
            <div className="signal-light amber" />
            <div className="signal-light green active" />
          </div>
          <div className="signal-readout">
            <strong>{latestPlan?.green_seconds ?? 0}s</strong>
            <span>{latestPlan?.priority ?? "normal"}</span>
            <span>{latestPlan?.decision_source ?? summary.metadata?.signal_decision_source ?? "safe_fallback"}</span>
          </div>
          <p className="signal-reason">{latestPlan?.reason ?? "No active timing plan"}</p>
          <button
            className="primary-button"
            disabled={busy}
            onClick={() =>
              runAction(
                () => api.optimize({ intersection_id: requireIntersection(), horizon_minutes: 15 }),
                "Signal plan optimized"
              )
            }
          >
            <Zap size={18} />
            Optimize
          </button>
        </section>

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

        <section className="control-panel">
          <div className="panel-heading">
            <BrainCircuit size={20} />
            <h2>Prediction</h2>
          </div>
          <div className="button-row">
            <button
              disabled={busy}
              onClick={() => runAction(trainPredictionModel, "Model trained successfully")}
            >
              <GitBranch size={18} />
              Train
            </button>
            <button
              disabled={busy}
              onClick={() =>
                runAction(
                  async () => {
                    const result = await api.predict({
                      intersection_id: requireIntersection(),
                      horizon_minutes: 30,
                      direction: predictionDirection,
                      weather_condition: predictionWeather,
                      pcu_total: predictionPcuTotal ? Number(predictionPcuTotal) : null,
                      hour_of_day: predictionHourOfDay === "" ? null : Number(predictionHourOfDay),
                      day_of_week: predictionDayOfWeek === "" ? null : Number(predictionDayOfWeek)
                    });
                    setLastPredictions((current) => ({
                      ...current,
                      [result.intersection_id]: result
                    }));
                  },
                  "Traffic prediction created"
                )
              }
            >
              <Play size={18} />
              Predict
            </button>
          </div>
          <div className="mini-grid">
            <label>
              Direction
              <select value={predictionDirection} onChange={(event) => setPredictionDirection(event.target.value)}>
                {DIRECTIONS.map((direction) => (
                  <option key={direction}>{direction}</option>
                ))}
              </select>
            </label>
            <label>
              Weather
              <select value={predictionWeather} onChange={(event) => setPredictionWeather(event.target.value)}>
                {WEATHER_OPTIONS.map((weather) => (
                  <option key={weather}>{weather}</option>
                ))}
              </select>
            </label>
            <label>
              Hour
              <input
                type="number"
                min="0"
                max="23"
                placeholder="Auto"
                value={predictionHourOfDay}
                onChange={(event) => setPredictionHourOfDay(event.target.value)}
              />
            </label>
            <label>
              Day
              <select value={predictionDayOfWeek} onChange={(event) => setPredictionDayOfWeek(event.target.value)}>
                <option value="">Auto</option>
                {DAY_OF_WEEK_OPTIONS.map((day) => (
                  <option key={day.value} value={day.value}>
                    {day.label}
                  </option>
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
                value={predictionPcuTotal}
                onChange={(event) => setPredictionPcuTotal(event.target.value)}
              />
            </label>
          </div>
          <PredictionInputs
            latestObservation={summary.observations?.[0]}
            direction={predictionDirection}
            weather={predictionWeather}
            pcuTotal={predictionPcuTotal}
            hourOfDay={predictionHourOfDay}
            dayOfWeek={predictionDayOfWeek}
            horizonMinutes={30}
          />
          <PredictionReadout prediction={lastPredictions[selectedIntersection] ?? summary.predictions?.[0]} />
        </section>

        <section className="control-panel">
          <div className="panel-heading">
            <TrafficCone size={20} />
            <h2>Traffic Log</h2>
          </div>
          <ManualObservationForm
            disabled={busy}
            intersectionId={selectedIntersection}
            vehicleCount={manualVehicleCount}
            setVehicleCount={setManualVehicleCount}
            avgSpeed={manualAvgSpeed}
            setAvgSpeed={setManualAvgSpeed}
            pcuTotal={manualPcuTotal}
            setPcuTotal={setManualPcuTotal}
            runAction={runAction}
          />
        </section>

        <section className="control-panel">
          <div className="panel-heading">
            <ShieldAlert size={20} />
            <h2>Emergency Priority</h2>
          </div>
          <EmergencyForm disabled={busy} intersectionId={selectedIntersection} runAction={runAction} />
          <div className="emergency-list">
            {activeEmergencies.map((event) => (
              <button
                key={event.id}
                className="emergency-item"
                onClick={() => runAction(() => api.clearEmergency(event.id), "Emergency cleared")}
              >
                <span>{event.vehicle_type}</span>
                <small>{event.direction}</small>
              </button>
            ))}
          </div>
          <EmergencyCorridorForm
            disabled={busy}
            activeEmergency={activeEmergencies[0]}
            intersections={intersections}
            selectedIntersection={selectedIntersection}
            runAction={runAction}
          />
        </section>
      </section>

      <section className="data-grid">
        <Timeline title="Recent Observations" icon={Activity} rows={summary.observations} />
        <Timeline title="Signal Plans" icon={RadioTower} rows={summary.signal_plans} plan />
        <Timeline title="Predictions" icon={Radar} rows={summary.predictions} prediction />
      </section>

      <IntersectionForm disabled={busy} runAction={runAction} />
      <PcuCalculator
        hasDetection={Boolean(detection)}
        showNotice={(message) => setNotice({ type: "success", message })}
        onApplyDetection={(result) => {
          setCorrectedVehicleCount(String(result.vehicleCount));
          setDetectionPcuTotal(result.pcuTotalText);
        }}
        onApplyManual={(result) => {
          setManualVehicleCount(result.vehicleCount);
          setManualPcuTotal(result.pcuTotalText);
        }}
        onApplyPrediction={(result) => setPredictionPcuTotal(result.pcuTotalText)}
      />
    </main>
  );
}

function PcuCalculator({ hasDetection, showNotice, onApplyDetection, onApplyManual, onApplyPrediction }) {
  const [isMinimized, setIsMinimized] = useState(false);
  const [counts, setCounts] = useState(createEmptyPcuCounts);
  const [position, setPosition] = useState(PCU_CALCULATOR_DEFAULT_POSITION);
  const dragState = useRef(null);
  const totals = useMemo(() => calculatePcuTotals(counts), [counts]);
  const pcuTotalText = formatPcuTotal(totals.pcuTotal);
  const applyResult = {
    vehicleCount: totals.vehicleCount,
    pcuTotal: totals.pcuTotal,
    pcuTotalText
  };

  function updateVehicleCount(vehicleKey, value) {
    setCounts((currentCounts) => ({
      ...currentCounts,
      [vehicleKey]: normalizePcuQuantity(value)
    }));
  }

  function startDrag(event) {
    if (event.button !== 0) return;
    const panel = event.currentTarget.closest(".pcu-calculator");
    const rect = panel.getBoundingClientRect();
    dragState.current = {
      pointerId: event.pointerId,
      offsetX: event.clientX - rect.left,
      offsetY: event.clientY - rect.top,
      width: rect.width,
      height: rect.height
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function moveDrag(event) {
    const activeDrag = dragState.current;
    if (!activeDrag || activeDrag.pointerId !== event.pointerId) return;

    const nextLeft = Math.min(
      Math.max(event.clientX - activeDrag.offsetX, 8),
      window.innerWidth - activeDrag.width - 8
    );
    const nextTop = Math.min(
      Math.max(event.clientY - activeDrag.offsetY, 8),
      window.innerHeight - activeDrag.height - 8
    );
    setPosition({
      left: nextLeft,
      top: nextTop,
      right: "auto",
      bottom: "auto"
    });
  }

  function stopDrag(event) {
    if (dragState.current?.pointerId === event.pointerId) {
      dragState.current = null;
    }
  }

  return (
    <aside
      className={`pcu-calculator ${isMinimized ? "minimized" : ""}`}
      style={position}
      aria-label="PCU calculator"
    >
      <div
        className="pcu-calculator-header"
        onPointerDown={startDrag}
        onPointerMove={moveDrag}
        onPointerUp={stopDrag}
        onPointerCancel={stopDrag}
      >
        <span className="pcu-title">
          <Calculator size={18} />
          PCU Calculator
        </span>
        <span className="pcu-header-total">{pcuTotalText} PCU</span>
        <button
          type="button"
          className="pcu-toggle"
          onPointerDown={(event) => event.stopPropagation()}
          onClick={() => setIsMinimized((current) => !current)}
          aria-expanded={!isMinimized}
          aria-label={isMinimized ? "Expand PCU calculator" : "Minimize PCU calculator"}
        >
          {isMinimized ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
        </button>
      </div>

      {!isMinimized && (
        <div className="pcu-calculator-body">
          <div className="pcu-total-grid" aria-live="polite">
            <div>
              <span>Vehicles</span>
              <strong>{totals.vehicleCount}</strong>
            </div>
            <div>
              <span>Total PCU</span>
              <strong>{pcuTotalText}</strong>
            </div>
          </div>

          <div className="pcu-vehicle-list">
            {PCU_VEHICLE_OPTIONS.map((vehicle) => {
              const quantity = normalizePcuQuantity(counts[vehicle.key]);
              const sliderMax = Math.max(PCU_QUANTITY_SLIDER_MAX, quantity);
              return (
                <label className="pcu-vehicle-row" key={vehicle.key}>
                  <span className="pcu-vehicle-name">
                    {vehicle.label}
                    <small>{vehicle.factor} PCU</small>
                  </span>
                  <input
                    type="number"
                    min="0"
                    inputMode="numeric"
                    value={quantity}
                    onChange={(event) => updateVehicleCount(vehicle.key, event.target.value)}
                    aria-label={`${vehicle.label} quantity`}
                  />
                  <input
                    type="range"
                    min="0"
                    max={sliderMax}
                    value={quantity}
                    onChange={(event) => updateVehicleCount(vehicle.key, event.target.value)}
                    aria-label={`${vehicle.label} quantity slider`}
                  />
                </label>
              );
            })}
          </div>

          <div className="pcu-actions">
            <button
              type="button"
              onClick={() => {
                setCounts(createEmptyPcuCounts());
                showNotice("PCU calculator reset");
              }}
              title="Reset PCU counts"
            >
              <RotateCcw size={16} />
              Reset
            </button>
            <button
              type="button"
              onClick={() => {
                onApplyManual(applyResult);
                showNotice("PCU applied to Traffic Log");
              }}
            >
              Traffic Log
            </button>
            <button
              type="button"
              onClick={() => {
                onApplyPrediction(applyResult);
                showNotice("PCU applied to Prediction");
              }}
            >
              Prediction
            </button>
            <button
              type="button"
              disabled={!hasDetection}
              onClick={() => {
                onApplyDetection(applyResult);
                showNotice("PCU applied to Frame Review");
              }}
            >
              Frame Review
            </button>
          </div>
        </div>
      )}
    </aside>
  );
}

function PredictionReadout({ prediction }) {
  if (!prediction) {
    return (
      <div className="prediction-readout muted">
        <span>Prediction</span>
        <strong>No forecast</strong>
      </div>
    );
  }

  return (
    <div className="prediction-readout">
      <span>{prediction.horizon_minutes} minute forecast</span>
      <div>
        <strong>{percent(prediction.predicted_density)}</strong>
        <small>{Math.round(prediction.predicted_vehicle_count)} vehicles</small>
      </div>
    </div>
  );
}

function PredictionInputs({ latestObservation, direction, weather, pcuTotal, hourOfDay, dayOfWeek, horizonMinutes }) {
  const selectedDay = DAY_OF_WEEK_OPTIONS.find((day) => String(day.value) === String(dayOfWeek));

  return (
    <div className="prediction-inputs">
      <div>
        <span>Latest Count</span>
        <strong>{latestObservation?.vehicle_count ?? 0}</strong>
      </div>
      <div>
        <span>Latest Density</span>
        <strong>{percent(latestObservation?.density)}</strong>
      </div>
      <div>
        <span>Direction</span>
        <strong>{direction}</strong>
      </div>
      <div>
        <span>Weather</span>
        <strong>{weather}</strong>
      </div>
      <div>
        <span>PCU</span>
        <strong>{pcuTotal || latestObservation?.pcu_total || "raw"}</strong>
      </div>
      <div>
        <span>Hour</span>
        <strong>{hourOfDay === "" ? "auto" : hourOfDay}</strong>
      </div>
      <div>
        <span>Day</span>
        <strong>{selectedDay?.label ?? "auto"}</strong>
      </div>
      <div>
        <span>Horizon</span>
        <strong>{horizonMinutes}m</strong>
      </div>
    </div>
  );
}

function IntersectionForm({ disabled, runAction }) {
  const [form, setForm] = useState({ name: "", latitude: "", longitude: "", lanes: 4, road_type: "urban" });

  return (
    <form
      className="inline-form"
      onSubmit={(event) => {
        event.preventDefault();
        runAction(
          () =>
            api.createIntersection({
              name: form.name,
              latitude: Number(form.latitude),
              longitude: Number(form.longitude),
              lanes: Number(form.lanes),
              road_type: form.road_type
            }),
          "Intersection created successfully"
        );
      }}
    >
      <strong>New Intersection</strong>
      <input placeholder="Name" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
      <input
        placeholder="Latitude"
        value={form.latitude}
        onChange={(event) => setForm({ ...form, latitude: event.target.value })}
      />
      <input
        placeholder="Longitude"
        value={form.longitude}
        onChange={(event) => setForm({ ...form, longitude: event.target.value })}
      />
      <input
        type="number"
        min="1"
        max="16"
        value={form.lanes}
        onChange={(event) => setForm({ ...form, lanes: event.target.value })}
      />
      <select value={form.road_type} onChange={(event) => setForm({ ...form, road_type: event.target.value })}>
        {ROAD_TYPE_OPTIONS.map((roadType) => (
          <option key={roadType.value} value={roadType.value}>
            {roadType.label}
          </option>
        ))}
      </select>
      <button disabled={disabled}>
        <Plus size={18} />
        Add
      </button>
    </form>
  );
}

function ManualObservationForm({
  disabled,
  intersectionId,
  vehicleCount,
  setVehicleCount,
  avgSpeed,
  setAvgSpeed,
  pcuTotal,
  setPcuTotal,
  runAction
}) {
  const [direction, setDirection] = useState("ALL");
  const [weatherCondition, setWeatherCondition] = useState("clear");
  return (
    <form
      className="compact-form"
      onSubmit={(event) => {
        event.preventDefault();
        runAction(
          () =>
            api.createObservation({
              intersection_id: intersectionId,
              direction,
              vehicle_count: Number(vehicleCount),
              avg_speed: avgSpeed === "" ? null : Number(avgSpeed),
              weather_condition: weatherCondition,
              pcu_total: pcuTotal ? Number(pcuTotal) : null,
              source: "manual"
            }),
          "Traffic observation logged successfully"
        );
      }}
    >
      <label>
        Vehicle Count
        <input
          type="number"
          min="0"
          value={vehicleCount}
          onChange={(event) => setVehicleCount(event.target.value)}
        />
      </label>
      <label>
        Avg Speed
        <input
          type="number"
          min="0"
          step="0.1"
          placeholder="Optional km/h"
          value={avgSpeed}
          onChange={(event) => setAvgSpeed(event.target.value)}
        />
      </label>
      <label>
        Direction
        <select value={direction} onChange={(event) => setDirection(event.target.value)}>
          {DIRECTIONS.map((item) => (
            <option key={item}>{item}</option>
          ))}
        </select>
      </label>
      <label>
        Weather
        <select value={weatherCondition} onChange={(event) => setWeatherCondition(event.target.value)}>
          {WEATHER_OPTIONS.map((item) => (
            <option key={item}>{item}</option>
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
          value={pcuTotal}
          onChange={(event) => setPcuTotal(event.target.value)}
        />
      </label>
      <button disabled={disabled || !intersectionId}>
        <Plus size={18} />
        Log
      </button>
    </form>
  );
}

function EmergencyForm({ disabled, intersectionId, runAction }) {
  const [form, setForm] = useState({ vehicle_type: "ambulance", direction: "northbound", severity: 8 });
  return (
    <form
      className="compact-form"
      onSubmit={(event) => {
        event.preventDefault();
        runAction(
          () =>
            form.vehicle_type === "none"
              ? api.clearIntersectionPriority(intersectionId)
              : api.createEmergency({
                  ...form,
                  intersection_id: intersectionId,
                  severity: Number(form.severity)
                }),
          form.vehicle_type === "none" ? "Intersection priority cleared" : "Emergency priority created"
        );
      }}
    >
      <label>
        Type
        <select
          value={form.vehicle_type}
          onChange={(event) => setForm({ ...form, vehicle_type: event.target.value })}
        >
          <option value="none">no priority vehicle</option>
          <option>ambulance</option>
          <option>fire truck</option>
          <option>police car</option>
          <option>police truck</option>
        </select>
      </label>
      {form.vehicle_type !== "none" && (
        <label>
        Direction
          <select
            value={form.direction}
            onChange={(event) => setForm({ ...form, direction: event.target.value })}
          >
            <option>northbound</option>
            <option>southbound</option>
            <option>eastbound</option>
            <option>westbound</option>
            <option>northeast</option>
            <option>northwest</option>
            <option>southeast</option>
            <option>southwest</option>
          </select>
        </label>
      )}
      {form.vehicle_type !== "none" && (
        <label>
          Severity
          <input
            type="number"
            min="1"
            max="10"
            value={form.severity}
            onChange={(event) => setForm({ ...form, severity: event.target.value })}
          />
        </label>
      )}
      <button disabled={disabled || !intersectionId}>
        <Ambulance size={18} />
        {form.vehicle_type === "none" ? "Clear Priority" : "Prioritize"}
      </button>
    </form>
  );
}

function EmergencyCorridorForm({ disabled, activeEmergency, intersections, selectedIntersection, runAction }) {
  const defaultIds = useMemo(
    () => intersections.map((intersection) => intersection.id),
    [intersections]
  );
  const [selectedIds, setSelectedIds] = useState(defaultIds);
  const [avgSpeedKmh, setAvgSpeedKmh] = useState(30);

  useEffect(() => {
    setSelectedIds(defaultIds);
  }, [defaultIds]);

  if (!activeEmergency) {
    return (
      <div className="corridor-box muted">
        <Route size={18} />
        <span>No active corridor</span>
      </div>
    );
  }

  return (
    <form
      className="corridor-box"
      onSubmit={(event) => {
        event.preventDefault();
        const orderedIds = [
          selectedIntersection,
          ...selectedIds.filter((id) => id !== selectedIntersection)
        ].filter(Boolean);
        runAction(
          () => api.createCorridor(activeEmergency.id, orderedIds, Number(avgSpeedKmh)),
          "Emergency corridor created successfully"
        );
      }}
    >
      <div className="corridor-title">
        <Route size={18} />
        <span>Green Corridor</span>
      </div>
      <label>
        Speed km/h
        <input
          type="number"
          min="5"
          max="120"
          value={avgSpeedKmh}
          onChange={(event) => setAvgSpeedKmh(event.target.value)}
        />
      </label>
      <div className="corridor-list">
        {intersections.map((intersection) => (
          <label key={intersection.id}>
            <input
              type="checkbox"
              checked={selectedIds.includes(intersection.id)}
              onChange={(event) => {
                setSelectedIds((current) =>
                  event.target.checked
                    ? [...new Set([...current, intersection.id])]
                    : current.filter((id) => id !== intersection.id)
                );
              }}
            />
            <span>{intersection.name}</span>
          </label>
        ))}
      </div>
      <button disabled={disabled || selectedIds.length === 0}>
        <Route size={18} />
        Create
      </button>
    </form>
  );
}

function Timeline({ title, icon: Icon, rows, plan, prediction }) {
  return (
    <section className="timeline-panel">
      <div className="panel-heading">
        <Icon size={20} />
        <h2>{title}</h2>
      </div>
      <div className="timeline">
        {rows?.length ? (
          rows.map((row) => (
            <article className="timeline-item" key={row.id}>
              <strong>
                {plan && `${row.green_seconds}s green`}
                {prediction && `${Math.round(row.predicted_vehicle_count)} vehicles`}
                {!plan && !prediction && `${row.vehicle_count} vehicles`}
              </strong>
              <span>
                {plan && row.priority}
                {prediction && percent(row.predicted_density)}
                {!plan && !prediction && percent(row.density)}
              </span>
              {plan && row.phases?.length > 0 && (
                <div className="phase-strip">
                  {row.phases.map((phase) => (
                    <span key={phase.id}>
                      {phase.direction} {phase.green_seconds}s
                    </span>
                  ))}
                </div>
              )}
              {!plan && !prediction && (
                <div className="meta-strip">
                  <span>{row.direction}</span>
                  <span>{row.weather_condition}</span>
                  {row.pcu_total !== null && row.pcu_total !== undefined && <span>{row.pcu_total} PCU</span>}
                </div>
              )}
              <small>{new Date(row.created_at ?? row.captured_at).toLocaleString()}</small>
            </article>
          ))
        ) : (
          <p className="empty-state">No records</p>
        )}
      </div>
    </section>
  );
}
