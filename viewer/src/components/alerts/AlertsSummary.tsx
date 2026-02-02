/**
 * Alerts Summary - Compact alert list for sidebar display
 */

import { Component, For, Show, createMemo } from 'solid-js';
import { missionStore } from '@/stores/missionStore';
import { timeStore } from '@/stores/timeStore';
import type { Alert } from '@/types';

interface AlertsSummaryProps {
  limit?: number;
}

export const AlertsSummary: Component<AlertsSummaryProps> = (props) => {
  const alerts = createMemo(() => {
    const all = missionStore.state.alerts;
    return props.limit ? all.slice(0, props.limit) : all;
  });

  const totalAlerts = () => missionStore.state.alerts.length;

  return (
    <div class="alerts-summary">
      <Show
        when={alerts().length > 0}
        fallback={
          <div class="no-alerts">
            <span class="check-icon">{'\u2713'}</span>
            <span>No active alerts</span>
          </div>
        }
      >
        <div class="alerts-list">
          <For each={alerts()}>
            {(alert) => <AlertSummaryItem alert={alert} />}
          </For>
        </div>

        <Show when={props.limit && totalAlerts() > props.limit}>
          <button
            class="view-all-btn"
            onClick={() => missionStore.setActiveWorkspace('anomaly-response')}
          >
            View all {totalAlerts()} alerts
          </button>
        </Show>
      </Show>

      <style>{`
        .alerts-summary {
          display: flex;
          flex-direction: column;
          gap: var(--space-2);
        }

        .no-alerts {
          display: flex;
          align-items: center;
          gap: var(--space-2);
          padding: var(--space-3);
          background: var(--alert-success-bg);
          border-radius: var(--radius-md);
          font-size: var(--text-sm);
          color: var(--alert-success);
        }

        .check-icon {
          font-size: 16px;
        }

        .alerts-list {
          display: flex;
          flex-direction: column;
          gap: var(--space-2);
        }

        .view-all-btn {
          width: 100%;
          padding: var(--space-2);
          background: transparent;
          border: 1px dashed var(--neutral-border);
          border-radius: var(--radius-md);
          color: var(--electric-teal);
          font-size: var(--text-xs);
          cursor: pointer;
        }

        .view-all-btn:hover {
          background: var(--slate-50);
          border-style: solid;
        }
      `}</style>
    </div>
  );
};

// Alert Summary Item
interface AlertSummaryItemProps {
  alert: Alert;
}

const AlertSummaryItem: Component<AlertSummaryItemProps> = (props) => {
  const handleClick = () => {
    timeStore.jumpToTime(props.alert.timestamp);
  };

  return (
    <button
      class="alert-summary-item"
      classList={{
        failure: props.alert.severity === 'failure',
        warning: props.alert.severity === 'warning',
        info: props.alert.severity === 'info',
      }}
      onClick={handleClick}
    >
      <span
        class="status-dot"
        classList={{
          'status-dot-failure': props.alert.severity === 'failure',
          'status-dot-warning': props.alert.severity === 'warning',
          'status-dot-info': props.alert.severity === 'info',
        }}
      />
      <div class="item-content">
        <span class="item-title">{props.alert.title}</span>
        <span class="item-time font-mono">
          {formatAlertTime(props.alert.timestamp)}
        </span>
      </div>

      <style>{`
        .alert-summary-item {
          display: flex;
          align-items: flex-start;
          gap: var(--space-2);
          padding: var(--space-2) var(--space-3);
          background: white;
          border: 1px solid var(--neutral-border);
          border-radius: var(--radius-md);
          cursor: pointer;
          text-align: left;
          width: 100%;
          transition: all var(--transition-fast);
        }

        .alert-summary-item:hover {
          border-color: var(--slate-300);
          background: var(--slate-50);
        }

        .alert-summary-item.failure {
          border-left: 3px solid var(--alert-failure);
        }

        .alert-summary-item.warning {
          border-left: 3px solid var(--alert-warning);
        }

        .alert-summary-item.info {
          border-left: 3px solid var(--alert-info);
        }

        .item-content {
          flex: 1;
          min-width: 0;
        }

        .item-title {
          display: block;
          font-size: var(--text-sm);
          color: var(--slate-700);
          margin-bottom: var(--space-1);
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .item-time {
          font-size: var(--text-xs);
          color: var(--slate-500);
        }
      `}</style>
    </button>
  );
};

function formatAlertTime(date: Date): string {
  return date.toISOString().slice(11, 19);
}
