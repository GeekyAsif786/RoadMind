import {
  Activity,
  Ambulance,
  BrainCircuit,
  Camera,
  CircleGauge,
  Crosshair,
  GitBranch,
  MapPin,
  Play,
  Plus,
  Radar,
  RadioTower,
  RefreshCw,
  ShieldAlert,
  TrafficCone,
  Zap
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import MetricCard from "./components/MetricCard.jsx";
import { api } from "./services/api.js";

const SELECTED_INTERSECTION_KEY = "traffic-manager:selected-intersection";

const emptySummary = {
  intersections: 0,
  active_emergencies: 0,
  latest_density: null,
  latest_vehicle_count: null,
  signal_plans: [],
  observations: [],
  emergencies: [],
  predictions: []
};

function percent(value) {
  if (value === null || value === undefined) return "0%";
  return `${Math.round(value * 100)}%`;
}

export default function App() {
  const [summary, setSummary] = useState(emptySummary);
  const [intersections, setIntersections] = useState([]);
  const [selectedIntersection, setSelectedIntersection] = useState(
    () => window.localStorage.getItem(SELECTED_INTERSECTION_KEY) ?? ""
  );
  const [status, setStatus] = useState("Connecting");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [detection, setDetection] = useState(null);
  const [detectionPreviewUrl, setDetectionPreviewUrl] = useState("");
  const [correctedVehicleCount, setCorrectedVehicleCount] = useState("");
  const [lastPredictions, setLastPredictions] = useState({});

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
      setNotice(error.message);
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
    setNotice("");
    try {
      await action();
      setNotice(success);
      await refresh();
    } catch (error) {
      setNotice(error.message);
    } finally {
      setBusy(false);
    }
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
            onClick={() => refresh(selectedIntersection)}
            title="Refresh"
            aria-label="Refresh"
          >
            <RefreshCw size={18} />
          </button>
        </div>
      </section>

      {notice && <div className="notice">{notice}</div>}

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
                        vehicle_count: Number(correctedVehicleCount),
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
              onClick={() => runAction(api.trainPrediction, "RandomForest model trained")}
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
                      horizon_minutes: 30
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
          <ManualObservationForm disabled={busy} intersectionId={selectedIntersection} onDone={refresh} />
          <PredictionReadout prediction={lastPredictions[selectedIntersection] ?? summary.predictions?.[0]} />
        </section>

        <section className="control-panel">
          <div className="panel-heading">
            <ShieldAlert size={20} />
            <h2>Emergency Priority</h2>
          </div>
          <EmergencyForm disabled={busy} intersectionId={selectedIntersection} onDone={refresh} />
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
        </section>
      </section>

      <section className="data-grid">
        <Timeline title="Recent Observations" icon={Activity} rows={summary.observations} />
        <Timeline title="Signal Plans" icon={RadioTower} rows={summary.signal_plans} plan />
        <Timeline title="Predictions" icon={Radar} rows={summary.predictions} prediction />
      </section>

      <IntersectionForm disabled={busy} onDone={refresh} />
    </main>
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

function IntersectionForm({ disabled, onDone }) {
  const [form, setForm] = useState({ name: "", latitude: "", longitude: "", lanes: 4 });

  return (
    <form
      className="inline-form"
      onSubmit={(event) => {
        event.preventDefault();
        api
          .createIntersection({
            name: form.name,
            latitude: Number(form.latitude),
            longitude: Number(form.longitude),
            lanes: Number(form.lanes)
          })
          .then(() => onDone());
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
      <button disabled={disabled}>
        <Plus size={18} />
        Add
      </button>
    </form>
  );
}

function ManualObservationForm({ disabled, intersectionId, onDone }) {
  const [vehicleCount, setVehicleCount] = useState(24);
  return (
    <form
      className="compact-form"
      onSubmit={(event) => {
        event.preventDefault();
        api
          .createObservation({
            intersection_id: intersectionId,
            vehicle_count: Number(vehicleCount),
            source: "manual"
          })
          .then(() => onDone(intersectionId));
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
      <button disabled={disabled || !intersectionId}>
        <Plus size={18} />
        Log
      </button>
    </form>
  );
}

function EmergencyForm({ disabled, intersectionId, onDone }) {
  const [form, setForm] = useState({ vehicle_type: "ambulance", direction: "northbound", severity: 8 });
  return (
    <form
      className="compact-form"
      onSubmit={(event) => {
        event.preventDefault();
        const request =
          form.vehicle_type === "none"
            ? api.clearIntersectionPriority(intersectionId)
            : api.createEmergency({
                ...form,
                intersection_id: intersectionId,
                severity: Number(form.severity)
              });
        request.then(() => onDone(intersectionId));
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
