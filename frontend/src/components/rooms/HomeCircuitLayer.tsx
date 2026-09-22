import { CircuitBackplane } from "./CircuitBackplane";
import type { RefObject } from "react";
import type { CircuitKey } from "./homeCircuit";
import { circuitNodes, circuitTraces, isRoomCircuit } from "./homeCircuit";

type HomeCircuitLayerProps = {
  activeCircuit: CircuitKey | null;
  activeAnchor: { key: CircuitKey; cx: number; cy: number } | null;
  hoverRef: RefObject<HTMLDivElement | null>;
};

const roomTails: Partial<Record<CircuitKey, string>> = {
  living: "H235 L320 398 L375 455 V505 L466 597",
  bedroom: "H430 L466 508 L488 540 V585",
  kitchen: "H570 L534 508 L512 540 V585",
  office: "H765 L680 398 L625 455 V505 L534 597",
};

function anchoredTrace(key: CircuitKey, d: string, anchor: { cx: number; cy: number }) {
  const cx = Number(anchor.cx.toFixed(1));
  const cy = Number(anchor.cy.toFixed(1));

  if (isRoomCircuit(key)) {
    const padY = Math.min(cy + 24, 300);
    const railY = Math.max(padY + 22, 320);
    return `M${cx} ${cy} V${padY.toFixed(1)} L${cx} ${railY.toFixed(1)} ${roomTails[key]}`;
  }

  return d.replace(/^M[\d.]+ [\d.]+/, `M${cx} ${cy}`);
}

export function HomeCircuitLayer({ activeCircuit, activeAnchor, hoverRef }: HomeCircuitLayerProps) {
  return (
    <>
      <svg className="circuit-layer" viewBox="0 0 1000 700" preserveAspectRatio="none" aria-hidden="true">
        <defs>
          <radialGradient id="circuitIdle" cx="500" cy="625" r="620" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="var(--hm-circuit-idle-0, rgba(0, 255, 240, 0.102))" />
            <stop offset="34%" stopColor="var(--hm-circuit-idle-1, rgba(0, 255, 240, 0.064))" />
            <stop offset="72%" stopColor="var(--hm-circuit-idle-2, rgba(0, 255, 240, 0.05))" />
            <stop offset="100%" stopColor="var(--hm-circuit-idle-3, rgba(0, 255, 240, 0.034))" />
          </radialGradient>
          <linearGradient id="circuitActive" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="var(--hm-circuit-active-0, #00f5ff)" stopOpacity="var(--hm-circuit-active-opacity-0, 0.82)" />
            <stop offset="55%" stopColor="var(--hm-circuit-active-1, #16f3be)" stopOpacity="var(--hm-circuit-active-opacity-1, 0.77)" />
            <stop offset="100%" stopColor="var(--hm-circuit-active-2, #c9ffff)" stopOpacity="var(--hm-circuit-active-opacity-2, 0.68)" />
          </linearGradient>
          <filter id="neonTrace" x="-35%" y="-35%" width="170%" height="170%">
            <feGaussianBlur stdDeviation="1.75" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        <CircuitBackplane />
        <g className="circuit-active-lines">
          {circuitTraces.map((trace) => (
            <path
              key={trace.key}
              className={`circuit-line circuit-${trace.key} ${activeCircuit === trace.key ? "active-glowing" : ""}`}
              d={
                activeCircuit === trace.key && activeAnchor?.key === trace.key
                  ? anchoredTrace(trace.key, trace.d, activeAnchor)
                  : trace.d
              }
            />
          ))}
        </g>
      </svg>

      <div className="circuit-hover-layer" ref={hoverRef} aria-hidden="true">
        <svg className="circuit-hover-svg" viewBox="0 0 1000 700" preserveAspectRatio="none">
          <CircuitBackplane className="circuit-backplane-hover" />
        </svg>
      </div>

      <svg className="nodes-layer" viewBox="0 0 1000 700" preserveAspectRatio="none" aria-hidden="true">
        <g className="circuit-nodes">
          {circuitNodes.map((node) => (
            <circle
              key={node.key}
              className={`circuit-node node-${node.key} ${activeCircuit === node.key ? "active-glowing" : ""}`}
              cx={activeAnchor?.key === node.key ? activeAnchor.cx : node.cx}
              cy={activeAnchor?.key === node.key ? activeAnchor.cy : node.cy}
              r="4"
            />
          ))}
        </g>
      </svg>
    </>
  );
}
