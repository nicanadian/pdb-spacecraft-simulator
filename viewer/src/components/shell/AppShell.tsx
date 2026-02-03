/**
 * App Shell - Main Application Layout
 * Provides the overall structure: header, sidebar nav, main content, footer
 */

import { Component, Show, createSignal, createEffect } from 'solid-js';
import { WorkspaceSwitcher } from './WorkspaceSwitcher';
import { ModeIndicator } from './ModeIndicator';
import { HeaderBar } from './HeaderBar';
import { FooterTimeline } from './FooterTimeline';
import { missionStore } from '../../stores/missionStore';

// Workspace components
import { MissionOverview } from '../../workspaces/MissionOverview';
import { ManeuverPlanning } from '../../workspaces/ManeuverPlanning';
import { VleoDragLifetime } from '../../workspaces/VleoDragLifetime';
import { AnomalyResponse } from '../../workspaces/AnomalyResponse';
import { PayloadOperations } from '../../workspaces/PayloadOperations';

import type { WorkspaceId } from '../../types';

export const AppShell: Component = () => {
  const [sidebarCollapsed, setSidebarCollapsed] = createSignal(false);

  const renderWorkspace = () => {
    switch (missionStore.state.activeWorkspace) {
      case 'mission-overview':
        return <MissionOverview />;
      case 'maneuver-planning':
        return <ManeuverPlanning />;
      case 'vleo-drag':
        return <VleoDragLifetime />;
      case 'anomaly-response':
        return <AnomalyResponse />;
      case 'payload-ops':
        return <PayloadOperations />;
      default:
        return <MissionOverview />;
    }
  };

  return (
    <div class="app-shell">
      {/* Left Sidebar Navigation */}
      <aside
        class="sidebar-nav"
        classList={{ collapsed: sidebarCollapsed() }}
      >
        <div class="sidebar-logo">
          <span class="logo-icon">&#9670;</span>
          <Show when={!sidebarCollapsed()}>
            <span class="logo-text">Mission Viz</span>
          </Show>
        </div>

        <WorkspaceSwitcher collapsed={sidebarCollapsed()} />

        <div class="sidebar-footer">
          <ModeIndicator collapsed={sidebarCollapsed()} />
          <a
            href="?page=docs"
            class="docs-link"
            classList={{ collapsed: sidebarCollapsed() }}
            title="Documentation"
          >
            <span class="docs-icon">📚</span>
            <Show when={!sidebarCollapsed()}>
              <span class="docs-text">Docs</span>
            </Show>
          </a>
          <button
            class="collapse-btn btn btn-ghost btn-icon"
            onClick={() => setSidebarCollapsed(!sidebarCollapsed())}
            title={sidebarCollapsed() ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            <span class="collapse-icon">
              {sidebarCollapsed() ? '\u203A' : '\u2039'}
            </span>
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <div class="main-area">
        {/* Header */}
        <HeaderBar />

        {/* Workspace Content */}
        <main class="workspace-content">
          {renderWorkspace()}
        </main>

        {/* Footer Timeline */}
        <FooterTimeline />
      </div>

      <style>{`
        .app-shell {
          display: flex;
          width: 100%;
          height: 100%;
          background: var(--ghost-slate);
        }

        /* Sidebar Navigation */
        .sidebar-nav {
          width: var(--sidebar-nav-width);
          min-width: var(--sidebar-nav-width);
          background: var(--deep-space-navy);
          display: flex;
          flex-direction: column;
          transition: width var(--transition-normal);
          z-index: var(--z-sticky);
        }

        .sidebar-nav:not(.collapsed) {
          width: 200px;
          min-width: 200px;
        }

        .sidebar-logo {
          height: var(--header-height);
          display: flex;
          align-items: center;
          gap: var(--space-3);
          padding: var(--space-4);
          border-bottom: 1px solid var(--slate-700);
        }

        .logo-icon {
          font-size: 20px;
          color: var(--electric-teal);
        }

        .logo-text {
          font-size: var(--text-sm);
          font-weight: var(--font-semibold);
          color: var(--ghost-slate);
          white-space: nowrap;
        }

        .sidebar-footer {
          margin-top: auto;
          padding: var(--space-3);
          border-top: 1px solid var(--slate-700);
          display: flex;
          flex-direction: column;
          gap: var(--space-2);
        }

        .docs-link {
          display: flex;
          align-items: center;
          gap: var(--space-3);
          padding: var(--space-2) var(--space-3);
          color: var(--slate-400);
          text-decoration: none;
          border-radius: var(--radius-sm);
          transition: all var(--transition-fast);
          font-size: var(--text-sm);
        }

        .docs-link.collapsed {
          justify-content: center;
          padding: var(--space-2);
        }

        .docs-link:hover {
          color: var(--electric-teal);
          background: var(--slate-800);
        }

        .docs-icon {
          font-size: 16px;
        }

        .docs-text {
          white-space: nowrap;
        }

        .collapse-btn {
          width: 100%;
          justify-content: center;
          color: var(--slate-400);
        }

        .collapse-btn:hover {
          color: var(--ghost-slate);
          background: var(--slate-800);
        }

        .collapse-icon {
          font-size: 18px;
        }

        /* Main Area */
        .main-area {
          flex: 1;
          display: flex;
          flex-direction: column;
          overflow: hidden;
          min-width: 0;
        }

        .workspace-content {
          flex: 1;
          overflow: hidden;
          position: relative;
        }
      `}</style>
    </div>
  );
};
