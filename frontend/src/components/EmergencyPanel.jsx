import { Ambulance, Route, ShieldAlert } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { api } from "../services/api.js";

export default function EmergencyPanel({
  busy,
  selectedIntersection,
  intersections,
  activeEmergencies,
  runAction
}) {
  return (
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
