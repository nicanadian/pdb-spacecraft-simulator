/**
 * Header Bar - Top navigation with context chips and actions
 */

import { Component, Show, createMemo } from 'solid-js';
import { missionStore } from '@/stores/missionStore';
import { timeStore } from '@/stores/timeStore';

export const HeaderBar: Component = () => {
  const runData = () => missionStore.state.runData;

  const workspaceTitle = createMemo(() => {
    switch (missionStore.state.activeWorkspace) {
      case 'mission-overview':
        return 'Mission Overview';
      case 'maneuver-planning':
        return 'Maneuver Planning';
      case 'vleo-drag':
        return 'VLEO & Lifetime';
      case 'anomaly-response':
        return 'Anomaly Response';
      case 'payload-ops':
        return 'Payload Operations';
      default:
        return 'Mission Visualization';
    }
  });

  const alertCount = () => missionStore.state.unacknowledgedCount;

  return (
    <header class="header-bar">
      <div class="header-left">
        <h1 class="workspace-title">{workspaceTitle()}</h1>
        <Show when={runData()}>
          <div class="context-chips">
            <span class="chip">
              <span class="chip-label">Plan</span>
              <span class="chip-value">{runData()!.manifest.planId}</span>
            </span>
            <span class="chip">
              <span class="chip-label">Fidelity</span>
              <span class="chip-value">{runData()!.manifest.fidelity}</span>
            </span>
            <span class="chip">
              <span class="chip-label">Duration</span>
              <span class="chip-value">{runData()!.manifest.durationHours}h</span>
            </span>
          </div>
        </Show>
      </div>

      <div class="header-right">
        <Show when={missionStore.state.branchState === 'active'}>
          <div class="branch-indicator">
            <span class="branch-mode-glow" />
            <span>Branching Mode</span>
            <button
              class="btn btn-sm btn-secondary"
              onClick={() => missionStore.exitBranchMode(false)}
            >
              Discard
            </button>
            <button
              class="btn btn-sm btn-primary"
              onClick={() => missionStore.exitBranchMode(true)}
            >
              Commit
            </button>
          </div>
        </Show>

        <Show when={alertCount() > 0}>
          <button
            class="alert-button"
            onClick={() => missionStore.setActiveWorkspace('anomaly-response')}
          >
            <span class="alert-icon">{'\u26A0'}</span>
            <span class="alert-count">{alertCount()}</span>
          </button>
        </Show>

        <div class="undo-redo">
          <button
            class="btn btn-ghost btn-icon"
            disabled={!missionStore.canUndo()}
            onClick={() => missionStore.undo()}
            title="Undo"
          >
            {'\u21B6'}
          </button>
          <button
            class="btn btn-ghost btn-icon"
            disabled={!missionStore.canRedo()}
            onClick={() => missionStore.redo()}
            title="Redo"
          >
            {'\u21B7'}
          </button>
        </div>
      </div>

      <style>{`
        .header-bar {
          height: var(--header-height);
          min-height: var(--header-height);
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 0 var(--space-4);
          background: white;
          border-bottom: 1px solid var(--neutral-border);
        }

        .header-left {
          display: flex;
          align-items: center;
          gap: var(--space-4);
        }

        .workspace-title {
          font-size: var(--text-lg);
          font-weight: var(--font-semibold);
          color: var(--slate-900);
          margin: 0;
        }

        .context-chips {
          display: flex;
          gap: var(--space-2);
        }

        .chip {
          display: flex;
          align-items: center;
          gap: var(--space-1);
          padding: var(--space-1) var(--space-2);
          background: var(--slate-100);
          border-radius: var(--radius-md);
          font-size: var(--text-xs);
        }

        .chip-label {
          color: var(--slate-500);
        }

        .chip-value {
          color: var(--slate-700);
          font-weight: var(--font-medium);
          font-family: var(--font-mono);
        }

        .header-right {
          display: flex;
          align-items: center;
          gap: var(--space-3);
        }

        .branch-indicator {
          display: flex;
          align-items: center;
          gap: var(--space-3);
          padding: var(--space-2) var(--space-3);
          background: rgba(8, 145, 178, 0.1);
          border: 1px solid var(--electric-teal);
          border-radius: var(--radius-md);
          font-size: var(--text-sm);
          color: var(--electric-teal);
        }

        .alert-button {
          display: flex;
          align-items: center;
          gap: var(--space-1);
          padding: var(--space-2) var(--space-3);
          background: var(--alert-failure-bg);
          border: 1px solid var(--alert-failure);
          border-radius: var(--radius-md);
          cursor: pointer;
          color: var(--alert-failure);
          font-size: var(--text-sm);
          font-weight: var(--font-medium);
        }

        .alert-button:hover {
          background: rgba(220, 38, 38, 0.15);
        }

        .alert-icon {
          font-size: 14px;
        }

        .alert-count {
          font-family: var(--font-mono);
        }

        .undo-redo {
          display: flex;
          gap: var(--space-1);
        }

        .undo-redo .btn {
          font-size: 16px;
        }
      `}</style>
    </header>
  );
};
