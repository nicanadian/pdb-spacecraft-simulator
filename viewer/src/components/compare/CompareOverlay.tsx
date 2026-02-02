/**
 * Compare Overlay - Visual diff between baseline and current/branch
 * Shows ambient baseline comparison in geometry and timeline
 */

import { Component, Show } from 'solid-js';
import { missionStore } from '@/stores/missionStore';

export const CompareOverlay: Component = () => {
  const isComparing = () =>
    missionStore.state.branchState === 'comparing' ||
    missionStore.state.baselineData !== null;

  return (
    <Show when={isComparing()}>
      <div class="compare-overlay">
        <div class="compare-legend glass-floating">
          <div class="legend-title">Comparison Mode</div>
          <div class="legend-items">
            <div class="legend-item">
              <span class="legend-line solid" />
              <span class="legend-label">Current</span>
            </div>
            <div class="legend-item">
              <span class="legend-line ghost" />
              <span class="legend-label">Baseline</span>
            </div>
            <Show when={missionStore.state.branchState === 'active'}>
              <div class="legend-item">
                <span class="legend-line dashed" />
                <span class="legend-label">What-If</span>
              </div>
            </Show>
          </div>
        </div>

        <style>{`
          .compare-overlay {
            position: absolute;
            top: 0;
            right: 0;
            z-index: var(--z-dropdown);
            pointer-events: none;
          }

          .compare-legend {
            margin: var(--space-4);
            padding: var(--space-3) var(--space-4);
            pointer-events: auto;
          }

          .legend-title {
            font-size: var(--text-xs);
            font-weight: var(--font-semibold);
            color: var(--slate-700);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: var(--space-2);
          }

          .legend-items {
            display: flex;
            flex-direction: column;
            gap: var(--space-2);
          }

          .legend-item {
            display: flex;
            align-items: center;
            gap: var(--space-2);
          }

          .legend-line {
            width: 24px;
            height: 2px;
          }

          .legend-line.solid {
            background: var(--electric-teal);
          }

          .legend-line.ghost {
            background: var(--color-baseline);
          }

          .legend-line.dashed {
            background: repeating-linear-gradient(
              to right,
              var(--electric-teal),
              var(--electric-teal) 4px,
              transparent 4px,
              transparent 8px
            );
          }

          .legend-label {
            font-size: var(--text-xs);
            color: var(--slate-600);
          }
        `}</style>
      </div>
    </Show>
  );
};
