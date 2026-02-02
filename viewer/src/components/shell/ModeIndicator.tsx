/**
 * Mode Indicator - Shows current command mode state
 * Critical safety feature: always visible indication of Read-Only vs Command-Capable
 */

import { Component, Show } from 'solid-js';
import { missionStore } from '@/stores/missionStore';

interface ModeIndicatorProps {
  collapsed: boolean;
}

export const ModeIndicator: Component<ModeIndicatorProps> = (props) => {
  const isCommandCapable = () => missionStore.state.commandMode === 'command-capable';
  const isInBranchMode = () => missionStore.state.branchState === 'active';

  const toggleMode = () => {
    // In a real system, this would require authentication/confirmation
    missionStore.setCommandMode(
      isCommandCapable() ? 'read-only' : 'command-capable'
    );
  };

  return (
    <div class="mode-indicator" classList={{ collapsed: props.collapsed }}>
      <button
        class="mode-button"
        classList={{
          'command-capable': isCommandCapable(),
          'read-only': !isCommandCapable(),
        }}
        onClick={toggleMode}
        title={isCommandCapable() ? 'Command-Capable Mode' : 'Read-Only Mode'}
      >
        <span class="mode-dot" />
        <Show when={!props.collapsed}>
          <span class="mode-label">
            {isCommandCapable() ? 'Command' : 'Read-Only'}
          </span>
        </Show>
      </button>

      <Show when={isInBranchMode() && !props.collapsed}>
        <div class="branch-badge">
          <span class="branch-mode-glow" />
          <span class="branch-label">What-If</span>
        </div>
      </Show>

      <style>{`
        .mode-indicator {
          display: flex;
          flex-direction: column;
          gap: var(--space-2);
        }

        .mode-indicator.collapsed {
          align-items: center;
        }

        .mode-button {
          display: flex;
          align-items: center;
          gap: var(--space-2);
          padding: var(--space-2) var(--space-3);
          border: 1px solid transparent;
          border-radius: var(--radius-md);
          cursor: pointer;
          font-size: var(--text-xs);
          font-weight: var(--font-medium);
          transition: all var(--transition-fast);
        }

        .mode-button.read-only {
          background: var(--slate-800);
          color: var(--slate-400);
          border-color: var(--slate-700);
        }

        .mode-button.command-capable {
          background: rgba(8, 145, 178, 0.1);
          color: var(--electric-teal);
          border-color: var(--electric-teal);
        }

        .mode-button:hover {
          opacity: 0.9;
        }

        .mode-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          flex-shrink: 0;
        }

        .read-only .mode-dot {
          background: var(--slate-500);
        }

        .command-capable .mode-dot {
          background: var(--electric-teal);
          box-shadow: 0 0 6px var(--electric-teal);
        }

        .mode-label {
          white-space: nowrap;
        }

        .mode-indicator.collapsed .mode-button {
          padding: var(--space-2);
          justify-content: center;
        }

        /* Branch Mode Badge */
        .branch-badge {
          display: flex;
          align-items: center;
          gap: var(--space-2);
          padding: var(--space-1) var(--space-3);
          background: rgba(8, 145, 178, 0.15);
          border-radius: var(--radius-md);
          font-size: var(--text-xs);
          color: var(--electric-teal);
        }

        .branch-label {
          font-weight: var(--font-medium);
        }
      `}</style>
    </div>
  );
};
