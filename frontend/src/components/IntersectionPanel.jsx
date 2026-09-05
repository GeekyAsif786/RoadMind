import { Plus } from "lucide-react";
import { useState } from "react";

import { api } from "../services/api.js";
import { ROAD_TYPE_OPTIONS } from "./constants.js";

export default function IntersectionPanel({ disabled, runAction }) {
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
