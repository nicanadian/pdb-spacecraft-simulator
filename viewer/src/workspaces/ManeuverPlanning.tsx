/**
 * Maneuver Planning Workspace
 * Intent-to-consequence analysis for orbit maneuvers
 */

import { Component, Show } from 'solid-js';
import { GeometryView } from '@/components/geometry/GeometryView';
import { SequencePanel } from '@/components/sequence/SequencePanel';
import { TimelinePanel } from '@/components/timeline/TimelinePanel';
import { missionStore } from '@/stores/missionStore';

export const ManeuverPlanning: Component = () => {
  return (
    <div class="maneuver-planning">
      {/* Left: Sequence Panel */}
      <aside class="sequence-panel-area glass-sidebar">
        <SequencePanel />
      </aside>

      {/* Center: Geometry View */}
      <div class="geometry-area">
        <GeometryView showGhostOrbit={missionStore.state.branchState !== 'none'} />
      </div>

      {/* Right: What-If Inspector */}
      <aside class="inspector-area glass-sidebar">
        <div class="inspector-header">
          <h3>Impact Analysis</h3>
          <Show when={missionStore.state.branchState === 'none'}>
            <button
              class="btn btn-primary btn-sm"
              onClick={() => missionStore.enterBranchMode()}
            >
              Start What-If
            </button>
          </Show>
        </div>

        <Show
          when={missionStore.state.branchState !== 'none'}
          fallback={
            <div class="empty-state">
              <p>Enter What-If mode to analyze maneuver impacts</p>
            </div>
          }
        >
          <div class="impact-content">
            <div class="branch-indicator">
              <span class="branch-mode-glow" />
              <span>Branching Mode Active</span>
            </div>
            <div class="impact-placeholder">
              <p class="text-slate-500 text-sm">
                Modify parameters in the sequence panel to see predicted impacts here.
              </p>
            </div>
          </div>
        </Show>
      </aside>

      {/* Bottom: Timeline with ghost tracks */}
      <div class="timeline-area">
        <TimelinePanel showGhostTrack={missionStore.state.branchState !== 'none'} />
      </div>

      <style>{`
        .maneuver-planning {
          display: grid;
          grid-template-columns: var(--panel-default-width) 1fr var(--panel-default-width);
          grid-template-rows: 1fr 120px;
          height: 100%;
        }

        .sequence-panel-area {
          grid-column: 1;
          grid-row: 1 / 3;
          background: var(--glass-bg);
          border-right: 1px solid var(--neutral-border);
          overflow: hidden;
        }

        .geometry-area {
          grid-column: 2;
          grid-row: 1;
          position: relative;
        }

        .inspector-area {
          grid-column: 3;
          grid-row: 1 / 3;
          background: var(--glass-bg);
          border-left: 1px solid var(--neutral-border);
          display: flex;
          flex-direction: column;
        }

        .inspector-header {
          padding: var(--space-4);
          border-bottom: 1px solid var(--neutral-border);
          display: flex;
          align-items: center;
          justify-content: space-between;
        }

        .inspector-header h3 {
          font-size: var(--text-sm);
          font-weight: var(--font-semibold);
          color: var(--slate-700);
          margin: 0;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .empty-state {
          flex: 1;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: var(--space-6);
          text-align: center;
          color: var(--slate-500);
        }

        .impact-content {
          flex: 1;
          padding: var(--space-4);
        }

        .branch-indicator {
          display: flex;
          align-items: center;
          gap: var(--space-2);
          padding: var(--space-3);
          background: rgba(8, 145, 178, 0.1);
          border-radius: var(--radius-md);
          margin-bottom: var(--space-4);
          font-size: var(--text-sm);
          color: var(--electric-teal);
        }

        .impact-placeholder {
          padding: var(--space-4);
          background: var(--slate-50);
          border-radius: var(--radius-md);
          border: 1px dashed var(--neutral-border);
        }

        .timeline-area {
          grid-column: 2;
          grid-row: 2;
          background: white;
          border-top: 1px solid var(--neutral-border);
        }
      `}</style>
    </div>
  );
};
