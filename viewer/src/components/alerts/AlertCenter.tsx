/**
 * Alert Center - Threaded alert visualization with causal connectors
 * Based on mockup: Threaded Alert & Consequence Center.png
 */

import { Component, For, Show, createMemo } from 'solid-js';
import { missionStore } from '@/stores/missionStore';
import { timeStore } from '@/stores/timeStore';
import type { Alert } from '@/types';

export const AlertCenter: Component = () => {
  const alerts = () => missionStore.state.alerts;

  // Group alerts by root cause
  const alertThreads = createMemo(() => {
    const threads: Map<string, Alert[]> = new Map();

    alerts().forEach((alert) => {
      const rootId = alert.rootCauseId || alert.id;
      if (!threads.has(rootId)) {
        threads.set(rootId, []);
      }
      threads.get(rootId)!.push(alert);
    });

    return Array.from(threads.entries()).map(([rootId, threadAlerts]) => ({
      rootId,
      root: threadAlerts.find((a) => a.id === rootId) || threadAlerts[0],
      consequences: threadAlerts.filter((a) => a.id !== rootId),
    }));
  });

  return (
    <div class="alert-center">
      {/* Left Navigation */}
      <nav class="alerts-nav">
        <NavItem icon={'\u2302'} label="Dashboard" />
        <NavItem icon={'\u26A0'} label="Alerts" active />
        <NavItem icon={'\u26A1'} label="Warnings" />
        <NavItem icon={'\u2699'} label="Settings" />
        <NavItem icon={'\u{1F4CA}'} label="Analysis" />
        <NavItem icon={'\u{1F4E1}'} label="Commands" />
      </nav>

      {/* Main Content */}
      <div class="alerts-main">
        <div class="alerts-header">
          <h2>Alerts Dashboard</h2>
          <div class="header-stats">
            <span class="stat">
              <span class="stat-value">{alerts().length}</span>
              <span class="stat-label">Total</span>
            </span>
            <span class="stat failure">
              <span class="stat-value">
                {alerts().filter((a) => a.severity === 'failure').length}
              </span>
              <span class="stat-label">Failures</span>
            </span>
            <span class="stat warning">
              <span class="stat-value">
                {alerts().filter((a) => a.severity === 'warning').length}
              </span>
              <span class="stat-label">Warnings</span>
            </span>
          </div>
        </div>

        <div class="alerts-content">
          <Show
            when={alertThreads().length > 0}
            fallback={
              <div class="empty-state">
                <div class="empty-icon">{'\u2713'}</div>
                <h3>No Active Alerts</h3>
                <p>All systems operating normally</p>
              </div>
            }
          >
            <div class="alert-threads">
              <For each={alertThreads()}>
                {(thread) => (
                  <AlertThread
                    root={thread.root}
                    consequences={thread.consequences}
                  />
                )}
              </For>
            </div>
          </Show>
        </div>
      </div>

      <style>{`
        .alert-center {
          display: flex;
          height: 100%;
          background: var(--ghost-slate);
        }

        /* Left Navigation */
        .alerts-nav {
          width: var(--sidebar-nav-width);
          background: var(--deep-space-navy);
          display: flex;
          flex-direction: column;
          padding: var(--space-2);
          gap: var(--space-1);
        }

        /* Main Content */
        .alerts-main {
          flex: 1;
          display: flex;
          flex-direction: column;
          overflow: hidden;
        }

        .alerts-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: var(--space-4) var(--space-6);
          background: white;
          border-bottom: 1px solid var(--neutral-border);
        }

        .alerts-header h2 {
          font-size: var(--text-xl);
          font-weight: var(--font-semibold);
          color: var(--slate-900);
          margin: 0;
        }

        .header-stats {
          display: flex;
          gap: var(--space-4);
        }

        .stat {
          display: flex;
          flex-direction: column;
          align-items: center;
          padding: var(--space-2) var(--space-3);
          border-radius: var(--radius-md);
          background: var(--slate-100);
        }

        .stat.failure {
          background: var(--alert-failure-bg);
          color: var(--alert-failure);
        }

        .stat.warning {
          background: var(--alert-warning-bg);
          color: var(--alert-warning);
        }

        .stat-value {
          font-size: var(--text-lg);
          font-weight: var(--font-bold);
          font-family: var(--font-mono);
        }

        .stat-label {
          font-size: var(--text-xs);
          color: var(--slate-500);
        }

        .stat.failure .stat-label,
        .stat.warning .stat-label {
          color: inherit;
          opacity: 0.8;
        }

        .alerts-content {
          flex: 1;
          overflow-y: auto;
          padding: var(--space-6);
        }

        .empty-state {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          height: 100%;
          text-align: center;
        }

        .empty-icon {
          width: 64px;
          height: 64px;
          border-radius: 50%;
          background: var(--alert-success-bg);
          color: var(--alert-success);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 32px;
          margin-bottom: var(--space-4);
        }

        .empty-state h3 {
          font-size: var(--text-lg);
          color: var(--slate-700);
          margin: 0 0 var(--space-2) 0;
        }

        .empty-state p {
          color: var(--slate-500);
          margin: 0;
        }

        .alert-threads {
          display: flex;
          flex-direction: column;
          gap: var(--space-6);
        }
      `}</style>
    </div>
  );
};

// Navigation Item
interface NavItemProps {
  icon: string;
  label: string;
  active?: boolean;
}

const NavItem: Component<NavItemProps> = (props) => {
  return (
    <button class="nav-item" classList={{ active: props.active }}>
      <span class="nav-icon">{props.icon}</span>
      <Show when={props.active}>
        <span class="active-indicator" />
      </Show>

      <style>{`
        .nav-item {
          width: 40px;
          height: 40px;
          border: none;
          background: transparent;
          color: var(--slate-400);
          cursor: pointer;
          border-radius: var(--radius-md);
          display: flex;
          align-items: center;
          justify-content: center;
          position: relative;
        }

        .nav-item:hover {
          background: var(--slate-800);
          color: var(--ghost-slate);
        }

        .nav-item.active {
          color: var(--electric-teal);
        }

        .nav-icon {
          font-size: 18px;
        }

        .active-indicator {
          position: absolute;
          left: 0;
          top: 50%;
          transform: translateY(-50%);
          width: 3px;
          height: 20px;
          background: var(--electric-teal);
          border-radius: 0 2px 2px 0;
        }
      `}</style>
    </button>
  );
};

// Alert Thread Component
interface AlertThreadProps {
  root: Alert;
  consequences: Alert[];
}

const AlertThread: Component<AlertThreadProps> = (props) => {
  return (
    <div class="alert-thread">
      {/* Root Alert */}
      <div class="thread-root">
        <AlertCard alert={props.root} isRoot />
      </div>

      {/* Consequences */}
      <Show when={props.consequences.length > 0}>
        <div class="thread-consequences">
          {/* Connector Line */}
          <svg class="connector-lines" preserveAspectRatio="none">
            <For each={props.consequences}>
              {(_, index) => (
                <path
                  class="connector-path"
                  d={`M 0 50 H 40 V ${50 + index() * 120} H 60`}
                  fill="none"
                  stroke="var(--slate-300)"
                  stroke-width="1"
                />
              )}
            </For>
          </svg>

          <div class="consequences-list">
            <For each={props.consequences}>
              {(consequence) => <AlertCard alert={consequence} />}
            </For>
          </div>
        </div>
      </Show>

      <style>{`
        .alert-thread {
          display: flex;
          gap: var(--space-4);
        }

        .thread-root {
          flex-shrink: 0;
        }

        .thread-consequences {
          flex: 1;
          display: flex;
          position: relative;
        }

        .connector-lines {
          position: absolute;
          left: -40px;
          top: 0;
          width: 60px;
          height: 100%;
          pointer-events: none;
        }

        .connector-path {
          stroke-dasharray: none;
        }

        .consequences-list {
          display: flex;
          flex-direction: column;
          gap: var(--space-3);
        }
      `}</style>
    </div>
  );
};

// Alert Card Component
interface AlertCardProps {
  alert: Alert;
  isRoot?: boolean;
}

const AlertCard: Component<AlertCardProps> = (props) => {
  const handleAction = (action: Alert['suggestedActions'][0]) => {
    console.log('Execute action:', action);
    // In a real implementation, this would trigger the action
  };

  return (
    <div
      class="alert-card glass-card"
      classList={{
        root: props.isRoot,
        failure: props.alert.severity === 'failure',
        warning: props.alert.severity === 'warning',
        info: props.alert.severity === 'info',
      }}
    >
      <div class="card-header">
        <span
          class="status-dot"
          classList={{
            'status-dot-failure': props.alert.severity === 'failure',
            'status-dot-warning': props.alert.severity === 'warning',
            'status-dot-info': props.alert.severity === 'info',
          }}
        />
        <span class="alert-title">{props.alert.title}</span>
      </div>

      <p class="alert-description">{props.alert.description}</p>

      <div class="alert-meta">
        <span class="alert-time font-mono">
          {timeStore.formatTime(props.alert.timestamp)}
        </span>
      </div>

      <Show when={props.alert.suggestedActions.length > 0}>
        <div class="alert-actions">
          <For each={props.alert.suggestedActions}>
            {(action) => (
              <button
                class="btn btn-primary btn-sm"
                onClick={() => handleAction(action)}
              >
                {action.label}
              </button>
            )}
          </For>
        </div>
      </Show>

      <style>{`
        .alert-card {
          width: 320px;
          position: relative;
        }

        .alert-card.root {
          width: 360px;
        }

        .alert-card::before {
          content: '';
          position: absolute;
          left: 0;
          top: 0;
          bottom: 0;
          width: 4px;
          border-radius: var(--radius-lg) 0 0 var(--radius-lg);
        }

        .alert-card.failure::before {
          background: var(--alert-failure);
        }

        .alert-card.warning::before {
          background: var(--alert-warning);
        }

        .alert-card.info::before {
          background: var(--alert-info);
        }

        .card-header {
          display: flex;
          align-items: center;
          gap: var(--space-2);
          margin-bottom: var(--space-2);
        }

        .alert-title {
          font-weight: var(--font-semibold);
          color: var(--slate-800);
        }

        .alert-description {
          font-size: var(--text-sm);
          color: var(--slate-600);
          margin: 0 0 var(--space-3) 0;
          line-height: var(--leading-relaxed);
        }

        .alert-meta {
          display: flex;
          align-items: center;
          gap: var(--space-2);
          margin-bottom: var(--space-3);
        }

        .alert-time {
          font-size: var(--text-xs);
          color: var(--slate-500);
        }

        .alert-actions {
          display: flex;
          gap: var(--space-2);
          padding-top: var(--space-3);
          border-top: 1px solid var(--neutral-border);
        }
      `}</style>
    </div>
  );
};
