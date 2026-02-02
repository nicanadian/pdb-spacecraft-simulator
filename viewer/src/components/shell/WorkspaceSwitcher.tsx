/**
 * Workspace Switcher - Navigation between task-oriented workspaces
 */

import { Component, For, Show } from 'solid-js';
import { missionStore } from '@/stores/missionStore';
import type { WorkspaceId } from '@/types';

interface WorkspaceItem {
  id: WorkspaceId;
  name: string;
  shortName: string;
  icon: string;
  description: string;
}

const workspaces: WorkspaceItem[] = [
  {
    id: 'mission-overview',
    name: 'Mission Overview',
    shortName: 'Overview',
    icon: '\u2302', // House
    description: 'Situational awareness and KPIs',
  },
  {
    id: 'maneuver-planning',
    name: 'Maneuver Planning',
    shortName: 'Maneuver',
    icon: '\u2794', // Arrow
    description: 'Intent to consequence analysis',
  },
  {
    id: 'vleo-drag',
    name: 'VLEO & Lifetime',
    shortName: 'VLEO',
    icon: '\u2601', // Cloud
    description: 'Atmospheric drag and lifetime',
  },
  {
    id: 'anomaly-response',
    name: 'Anomaly Response',
    shortName: 'Anomaly',
    icon: '\u26A0', // Warning
    description: 'Root cause and recovery',
  },
  {
    id: 'payload-ops',
    name: 'Payload Operations',
    shortName: 'Payload',
    icon: '\u2316', // Target
    description: 'Targeting and downlink',
  },
];

interface WorkspaceSwitcherProps {
  collapsed: boolean;
}

export const WorkspaceSwitcher: Component<WorkspaceSwitcherProps> = (props) => {
  const handleSelect = (id: WorkspaceId) => {
    missionStore.setActiveWorkspace(id);
  };

  return (
    <nav class="workspace-switcher">
      <For each={workspaces}>
        {(workspace) => (
          <button
            class="workspace-item"
            classList={{
              active: missionStore.state.activeWorkspace === workspace.id,
              collapsed: props.collapsed,
            }}
            onClick={() => handleSelect(workspace.id)}
            title={workspace.description}
          >
            <span class="workspace-icon">{workspace.icon}</span>
            <Show when={!props.collapsed}>
              <span class="workspace-name">{workspace.name}</span>
            </Show>
            <Show when={missionStore.state.activeWorkspace === workspace.id}>
              <span class="active-indicator" />
            </Show>
          </button>
        )}
      </For>

      <style>{`
        .workspace-switcher {
          display: flex;
          flex-direction: column;
          gap: var(--space-1);
          padding: var(--space-3);
        }

        .workspace-item {
          display: flex;
          align-items: center;
          gap: var(--space-3);
          padding: var(--space-3);
          border: none;
          background: transparent;
          color: var(--slate-400);
          border-radius: var(--radius-md);
          cursor: pointer;
          transition: all var(--transition-fast);
          text-align: left;
          font-size: var(--text-sm);
          position: relative;
        }

        .workspace-item.collapsed {
          justify-content: center;
          padding: var(--space-3);
        }

        .workspace-item:hover {
          background: var(--slate-800);
          color: var(--ghost-slate);
        }

        .workspace-item.active {
          background: var(--slate-800);
          color: var(--electric-teal);
        }

        .workspace-icon {
          font-size: 18px;
          width: 24px;
          text-align: center;
          flex-shrink: 0;
        }

        .workspace-name {
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .active-indicator {
          position: absolute;
          left: 0;
          top: 50%;
          transform: translateY(-50%);
          width: 3px;
          height: 24px;
          background: var(--electric-teal);
          border-radius: 0 2px 2px 0;
        }
      `}</style>
    </nav>
  );
};
