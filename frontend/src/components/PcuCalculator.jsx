import {
  Calculator,
  ChevronDown,
  ChevronUp,
  RotateCcw
} from "lucide-react";
import { useMemo, useRef, useState } from "react";

import {
  PCU_CALCULATOR_DEFAULT_POSITION,
  PCU_QUANTITY_SLIDER_MAX,
  PCU_VEHICLE_OPTIONS,
  calculatePcuTotals,
  createEmptyPcuCounts,
  formatPcuTotal,
  normalizePcuQuantity
} from "./constants.js";

export default function PcuCalculator({ hasDetection, showNotice, onApplyDetection, onApplyManual, onApplyPrediction }) {
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
