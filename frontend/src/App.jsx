import {
  Activity,
  Ambulance,
  CircleGauge,
  KeyRound,
  MapPin,
  Plus,
  Radar,
  RadioTower,
  RefreshCw,
  TrafficCone,
  Zap
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import DetectionPanel from "./components/DetectionPanel.jsx";
import EmergencyPanel from "./components/EmergencyPanel.jsx";
import IntersectionPanel from "./components/IntersectionPanel.jsx";
import MetricCard from "./components/MetricCard.jsx";
import PcuCalculator from "./components/PcuCalculator.jsx";
import PredictionPanel from "./components/PredictionPanel.jsx";
import {
  DIRECTIONS,
  SELECTED_INTERSECTION_KEY,
  TRAINING_MAX_POLLS,
  TRAINING_POLL_INTERVAL_MS,
  WEATHER_OPTIONS,
  emptySummary,
  percent
} from "./components/constants.js";
import { api } from "./services/api.js";

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

        <DetectionPanel
          busy={busy}
          selectedIntersection={selectedIntersection}
          runAction={runAction}
          requireIntersection={requireIntersection}
          detection={detection}
          setDetection={setDetection}
          detectionPreviewUrl={detectionPreviewUrl}
          setDetectionPreviewUrl={setDetectionPreviewUrl}
          correctedVehicleCount={correctedVehicleCount}
          setCorrectedVehicleCount={setCorrectedVehicleCount}
          detectionDirection={detectionDirection}
          setDetectionDirection={setDetectionDirection}
          detectionWeather={detectionWeather}
          setDetectionWeather={setDetectionWeather}
          detectionPcuTotal={detectionPcuTotal}
          setDetectionPcuTotal={setDetectionPcuTotal}
        />

        <PredictionPanel
          busy={busy}
          selectedIntersection={selectedIntersection}
          summary={summary}
          runAction={runAction}
          requireIntersection={requireIntersection}
          trainPredictionModel={trainPredictionModel}
          predictionDirection={predictionDirection}
          setPredictionDirection={setPredictionDirection}
          predictionWeather={predictionWeather}
          setPredictionWeather={setPredictionWeather}
          predictionPcuTotal={predictionPcuTotal}
          setPredictionPcuTotal={setPredictionPcuTotal}
          predictionHourOfDay={predictionHourOfDay}
          setPredictionHourOfDay={setPredictionHourOfDay}
          predictionDayOfWeek={predictionDayOfWeek}
          setPredictionDayOfWeek={setPredictionDayOfWeek}
          lastPredictions={lastPredictions}
          setLastPredictions={setLastPredictions}
        />

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

        <EmergencyPanel
          busy={busy}
          selectedIntersection={selectedIntersection}
          intersections={intersections}
          activeEmergencies={activeEmergencies}
          runAction={runAction}
        />
      </section>

      <section className="data-grid">
        <Timeline title="Recent Observations" icon={Activity} rows={summary.observations} />
        <Timeline title="Signal Plans" icon={RadioTower} rows={summary.signal_plans} plan />
        <Timeline title="Predictions" icon={Radar} rows={summary.predictions} prediction />
      </section>

      <IntersectionPanel disabled={busy} runAction={runAction} />
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
