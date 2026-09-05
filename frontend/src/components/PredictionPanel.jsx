import { BrainCircuit, GitBranch, Play } from "lucide-react";

import { api } from "../services/api.js";
import { DAY_OF_WEEK_OPTIONS, DIRECTIONS, WEATHER_OPTIONS, percent } from "./constants.js";

export default function PredictionPanel({
  busy,
  selectedIntersection,
  summary,
  runAction,
  requireIntersection,
  trainPredictionModel,
  predictionDirection,
  setPredictionDirection,
  predictionWeather,
  setPredictionWeather,
  predictionPcuTotal,
  setPredictionPcuTotal,
  predictionHourOfDay,
  setPredictionHourOfDay,
  predictionDayOfWeek,
  setPredictionDayOfWeek,
  lastPredictions,
  setLastPredictions
}) {
  return (
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
