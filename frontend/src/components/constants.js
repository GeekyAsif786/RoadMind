// Shared constants and pure helpers used by the dashboard panels.
// Extracted from App.jsx unchanged to keep behavior identical across the split.

export const SELECTED_INTERSECTION_KEY = "traffic-manager:selected-intersection";
export const DIRECTIONS = ["ALL", "N", "S", "E", "W", "NE", "NW", "SE", "SW"];
export const WEATHER_OPTIONS = ["clear", "light_rain", "heavy_rain", "fog", "smog"];
export const ROAD_TYPE_OPTIONS = [
  { value: "urban", label: "Urban arterial" },
  { value: "highway", label: "Highway / expressway" },
  { value: "service", label: "Service road" }
];
export const DAY_OF_WEEK_OPTIONS = [
  { value: 0, label: "Monday" },
  { value: 1, label: "Tuesday" },
  { value: 2, label: "Wednesday" },
  { value: 3, label: "Thursday" },
  { value: 4, label: "Friday" },
  { value: 5, label: "Saturday" },
  { value: 6, label: "Sunday" }
];
export const PCU_QUANTITY_SLIDER_MAX = 100;
export const PCU_CALCULATOR_DEFAULT_POSITION = { right: 24, bottom: 24 };
export const TRAINING_POLL_INTERVAL_MS = 1500;
export const TRAINING_MAX_POLLS = 80;
export const PCU_VEHICLE_OPTIONS = [
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

export const emptySummary = {
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

export function percent(value) {
  if (value === null || value === undefined) return "0%";
  return `${Math.round(value * 100)}%`;
}

export function createEmptyPcuCounts() {
  return PCU_VEHICLE_OPTIONS.reduce((counts, vehicle) => ({ ...counts, [vehicle.key]: 0 }), {});
}

export function normalizePcuQuantity(value) {
  const parsedValue = Number(value);
  if (!Number.isFinite(parsedValue) || parsedValue < 0) return 0;
  return Math.floor(parsedValue);
}

export function formatPcuTotal(value) {
  if (Number.isInteger(value)) return String(value);
  return value.toFixed(2).replace(/\.?0+$/, "");
}

export function calculatePcuTotals(counts) {
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
