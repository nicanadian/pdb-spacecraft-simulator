/**
 * VLEO Drag & Lifetime Workspace
 * Atmospheric environment and orbit lifetime analysis
 */

import { Component } from 'solid-js';
import { GeometryView } from '@/components/geometry/GeometryView';
import { TimelinePanel } from '@/components/timeline/TimelinePanel';

export const VleoDragLifetime: Component = () => {
  return (
    <div class="vleo-workspace">
      {/* Center: Geometry with density overlay */}
      <div class="geometry-area">
        <GeometryView showDensityLayer={true} />

        {/* Floating Density Legend */}
        <div class="density-legend glass-floating">
          <div class="legend-header">Atmospheric Density</div>
          <div class="legend-gradient">
            <div class="gradient-bar" />
            <div class="gradient-labels">
              <span>Low</span>
              <span>High</span>
            </div>
          </div>
          <div class="legend-info">
            <span class="info-label">Current Alt:</span>
            <span class="info-value font-mono">--</span>
          </div>
        </div>
      </div>

      {/* Right: Lifetime Metrics */}
      <aside class="metrics-panel glass-sidebar">
        <div class="panel-header">
          <h3>Lifetime Analysis</h3>
        </div>

        <div class="panel-content">
          <div class="metric-card">
            <span class="metric-label">Estimated Lifetime</span>
            <span class="metric-value font-mono">-- days</span>
            <span class="metric-subtext">At current altitude</span>
          </div>

          <div class="metric-card">
            <span class="metric-label">Mean Drag Acceleration</span>
            <span class="metric-value font-mono">-- m/s{'\u00B2'}</span>
          </div>

          <div class="metric-card">
            <span class="metric-label">Altitude Decay Rate</span>
            <span class="metric-value font-mono">-- km/day</span>
          </div>

          <div class="metric-card warning">
            <span class="metric-label">Re-entry Threshold</span>
            <span class="metric-value font-mono">120 km</span>
            <span class="metric-subtext">Mission ends below this altitude</span>
          </div>
        </div>

        <div class="panel-actions">
          <button class="btn btn-secondary btn-sm">
            Run Lifetime Prediction
          </button>
        </div>
      </aside>

      {/* Bottom: Timeline with altitude profile */}
      <div class="timeline-area">
        <TimelinePanel showAltitudeProfile={true} />
      </div>

      <style>{`
        .vleo-workspace {
          display: grid;
          grid-template-columns: 1fr var(--panel-default-width);
          grid-template-rows: 1fr 140px;
          height: 100%;
        }

        .geometry-area {
          grid-column: 1;
          grid-row: 1;
          position: relative;
        }

        .density-legend {
          position: absolute;
          bottom: var(--space-4);
          left: var(--space-4);
          width: 200px;
          padding: var(--space-3);
        }

        .legend-header {
          font-size: var(--text-xs);
          font-weight: var(--font-semibold);
          color: var(--slate-700);
          margin-bottom: var(--space-2);
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .legend-gradient {
          margin-bottom: var(--space-2);
        }

        .gradient-bar {
          height: 12px;
          border-radius: var(--radius-sm);
          background: linear-gradient(
            to right,
            rgba(8, 145, 178, 0.1),
            rgba(8, 145, 178, 0.3),
            rgba(8, 145, 178, 0.6),
            rgba(245, 158, 11, 0.6),
            rgba(220, 38, 38, 0.6)
          );
        }

        .gradient-labels {
          display: flex;
          justify-content: space-between;
          font-size: var(--text-xs);
          color: var(--slate-500);
          margin-top: var(--space-1);
        }

        .legend-info {
          display: flex;
          justify-content: space-between;
          font-size: var(--text-xs);
          padding-top: var(--space-2);
          border-top: 1px solid var(--neutral-border);
        }

        .info-label {
          color: var(--slate-500);
        }

        .info-value {
          color: var(--slate-700);
        }

        .metrics-panel {
          grid-column: 2;
          grid-row: 1 / 3;
          background: var(--glass-bg);
          border-left: 1px solid var(--neutral-border);
          display: flex;
          flex-direction: column;
        }

        .panel-header {
          padding: var(--space-4);
          border-bottom: 1px solid var(--neutral-border);
        }

        .panel-header h3 {
          font-size: var(--text-sm);
          font-weight: var(--font-semibold);
          color: var(--slate-700);
          margin: 0;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .panel-content {
          flex: 1;
          padding: var(--space-4);
          display: flex;
          flex-direction: column;
          gap: var(--space-3);
          overflow-y: auto;
        }

        .metric-card {
          padding: var(--space-3);
          background: white;
          border: 1px solid var(--neutral-border);
          border-radius: var(--radius-md);
        }

        .metric-card.warning {
          border-color: var(--alert-warning);
          background: var(--alert-warning-bg);
        }

        .metric-label {
          display: block;
          font-size: var(--text-xs);
          color: var(--slate-500);
          margin-bottom: var(--space-1);
        }

        .metric-value {
          display: block;
          font-size: var(--text-lg);
          font-weight: var(--font-semibold);
          color: var(--slate-800);
        }

        .metric-subtext {
          display: block;
          font-size: var(--text-xs);
          color: var(--slate-400);
          margin-top: var(--space-1);
        }

        .panel-actions {
          padding: var(--space-4);
          border-top: 1px solid var(--neutral-border);
        }

        .panel-actions .btn {
          width: 100%;
        }

        .timeline-area {
          grid-column: 1;
          grid-row: 2;
          background: white;
          border-top: 1px solid var(--neutral-border);
        }
      `}</style>
    </div>
  );
};
