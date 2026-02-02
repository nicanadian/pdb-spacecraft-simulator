/**
 * Telemetry Inspector - Real-time spacecraft state display
 * Based on mockup: The High-Fidelity Workspace.png
 */

import { Component, Show, createSignal, createEffect } from 'solid-js';
import { selectionStore } from '@/stores/selectionStore';
import { timeStore } from '@/stores/timeStore';
import { cesiumService } from '@/services/cesiumService';

interface TelemetryInspectorProps {
  onClose: () => void;
}

interface TelemetryData {
  altitude: number | null;
  inclination: number | null;
  orbitalPeriod: number | null;
  apogee: number | null;
  perigee: number | null;
  semimajorAxis: number | null;
  speed: number | null;
  latitude: number | null;
  longitude: number | null;
}

export const TelemetryInspector: Component<TelemetryInspectorProps> = (props) => {
  const [telemetry, setTelemetry] = createSignal<TelemetryData>({
    altitude: null,
    inclination: null,
    orbitalPeriod: null,
    apogee: null,
    perigee: null,
    semimajorAxis: null,
    speed: null,
    latitude: null,
    longitude: null,
  });

  const [expanded, setExpanded] = createSignal(false);

  const entityName = () => {
    const entityId = selectionStore.selectedEntity();
    if (!entityId) return 'Unknown';
    // Capitalize and format
    return entityId.charAt(0).toUpperCase() + entityId.slice(1).replace(/-/g, ' ');
  };

  // Update telemetry periodically
  createEffect(() => {
    const entityId = selectionStore.selectedEntity();
    if (!entityId) return;

    // In a real implementation, this would query the Cesium entity's position
    // and calculate orbital elements
    const updateTelemetry = () => {
      // Placeholder values - would be computed from Cesium entity
      setTelemetry({
        altitude: 405 + Math.random() * 10,
        inclination: 51.6,
        orbitalPeriod: 92.7,
        apogee: 410,
        perigee: 400,
        semimajorAxis: 6783,
        speed: 7.66 + Math.random() * 0.01,
        latitude: 45 + Math.sin(Date.now() / 10000) * 50,
        longitude: (Date.now() / 1000) % 360 - 180,
      });
    };

    updateTelemetry();
    const interval = setInterval(updateTelemetry, 1000);

    return () => clearInterval(interval);
  });

  const formatValue = (value: number | null, decimals: number = 1): string => {
    if (value === null) return '--';
    return value.toFixed(decimals);
  };

  return (
    <div class="telemetry-inspector">
      <div class="inspector-header">
        <div class="entity-info">
          <span class="entity-icon">{'\u{1F6F0}'}</span>
          <span class="entity-name">{entityName()}</span>
        </div>
        <button class="close-btn" onClick={props.onClose}>
          {'\u2715'}
        </button>
      </div>

      <div class="inspector-content">
        <div class="telemetry-grid">
          <TelemetryRow
            label="Altitude"
            value={formatValue(telemetry().altitude)}
            unit="km"
          />
          <TelemetryRow
            label="Inclination"
            value={formatValue(telemetry().inclination)}
            unit={'\u00B0'}
          />
          <TelemetryRow
            label="Orbital Period"
            value={formatValue(telemetry().orbitalPeriod)}
            unit="min"
          />
          <TelemetryRow
            label="Apogee"
            value={formatValue(telemetry().apogee)}
            unit="km"
          />
          <TelemetryRow
            label="Perigee"
            value={formatValue(telemetry().perigee)}
            unit="km"
          />
          <TelemetryRow
            label="Speed"
            value={formatValue(telemetry().speed, 2)}
            unit="km/s"
          />
        </div>

        <Show when={expanded()}>
          <div class="telemetry-grid expanded">
            <TelemetryRow
              label="Semi-major Axis"
              value={formatValue(telemetry().semimajorAxis)}
              unit="km"
            />
            <TelemetryRow
              label="Latitude"
              value={formatValue(telemetry().latitude)}
              unit={'\u00B0'}
            />
            <TelemetryRow
              label="Longitude"
              value={formatValue(telemetry().longitude)}
              unit={'\u00B0'}
            />
          </div>
        </Show>

        <button
          class="expand-btn"
          onClick={() => setExpanded(!expanded())}
        >
          {expanded() ? 'Show less' : 'Browse details'}
          <span class="expand-icon">{expanded() ? '\u25B2' : '\u25BC'}</span>
        </button>
      </div>

      <style>{`
        .telemetry-inspector {
          display: flex;
          flex-direction: column;
          height: 100%;
        }

        .inspector-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: var(--space-3) var(--space-4);
          border-bottom: 1px solid var(--neutral-border);
        }

        .entity-info {
          display: flex;
          align-items: center;
          gap: var(--space-2);
        }

        .entity-icon {
          font-size: 18px;
        }

        .entity-name {
          font-size: var(--text-sm);
          font-weight: var(--font-semibold);
          color: var(--slate-800);
        }

        .close-btn {
          width: 24px;
          height: 24px;
          border: none;
          background: transparent;
          color: var(--slate-500);
          cursor: pointer;
          border-radius: var(--radius-sm);
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .close-btn:hover {
          background: var(--slate-100);
          color: var(--slate-700);
        }

        .inspector-content {
          flex: 1;
          overflow-y: auto;
          padding: var(--space-4);
        }

        .telemetry-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: var(--space-2);
        }

        .telemetry-grid.expanded {
          margin-top: var(--space-3);
          padding-top: var(--space-3);
          border-top: 1px solid var(--neutral-border);
        }

        .expand-btn {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: var(--space-2);
          width: 100%;
          margin-top: var(--space-4);
          padding: var(--space-2);
          background: transparent;
          border: none;
          color: var(--electric-teal);
          font-size: var(--text-xs);
          cursor: pointer;
        }

        .expand-btn:hover {
          text-decoration: underline;
        }

        .expand-icon {
          font-size: 10px;
        }
      `}</style>
    </div>
  );
};

// Telemetry Row Component
interface TelemetryRowProps {
  label: string;
  value: string;
  unit: string;
}

const TelemetryRow: Component<TelemetryRowProps> = (props) => {
  return (
    <div class="telemetry-row">
      <span class="row-label">{props.label}</span>
      <span class="row-value font-mono">
        {props.value}
        <span class="row-unit">{props.unit}</span>
      </span>

      <style>{`
        .telemetry-row {
          display: flex;
          flex-direction: column;
          padding: var(--space-2);
          background: white;
          border: 1px solid var(--neutral-border);
          border-radius: var(--radius-sm);
        }

        .row-label {
          font-size: var(--text-xs);
          color: var(--slate-500);
          margin-bottom: var(--space-1);
        }

        .row-value {
          font-size: var(--text-sm);
          font-weight: var(--font-semibold);
          color: var(--slate-800);
        }

        .row-unit {
          font-size: var(--text-xs);
          color: var(--slate-500);
          margin-left: var(--space-1);
          font-weight: var(--font-normal);
        }
      `}</style>
    </div>
  );
};
