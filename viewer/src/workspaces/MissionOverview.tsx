/**
 * Mission Overview Workspace
 * Primary workspace for situational awareness and KPI monitoring
 */

import { Component, onMount, onCleanup, createSignal, Show } from 'solid-js';
import { GeometryView } from '@/components/geometry/GeometryView';
import { TimelinePanel } from '@/components/timeline/TimelinePanel';
import { AlertsSummary } from '@/components/alerts/AlertsSummary';
import { missionStore } from '@/stores/missionStore';

export const MissionOverview: Component = () => {
  const [rightPanelCollapsed, setRightPanelCollapsed] = createSignal(false);

  return (
    <div class="mission-overview">
      {/* Main 3D View */}
      <div class="geometry-area">
        <GeometryView />
      </div>

      {/* Right Panel: KPIs and Alerts */}
      <aside
        class="right-panel glass-sidebar"
        classList={{ collapsed: rightPanelCollapsed() }}
      >
        <button
          class="collapse-toggle"
          onClick={() => setRightPanelCollapsed(!rightPanelCollapsed())}
        >
          {rightPanelCollapsed() ? '\u2039' : '\u203A'}
        </button>

        <Show when={!rightPanelCollapsed()}>
          <div class="panel-content">
            <section class="kpi-section">
              <h3 class="section-title">Mission Status</h3>
              <div class="kpi-grid">
                <KpiCard
                  label="Elapsed Time"
                  value={formatElapsedTime(missionStore.state.runData?.manifest.durationHours || 0)}
                  unit=""
                />
                <KpiCard
                  label="Events"
                  value={missionStore.state.runData?.events.length || 0}
                  unit=""
                  alert={missionStore.state.unacknowledgedCount > 0}
                />
                <KpiCard
                  label="Contacts"
                  value={missionStore.state.runData?.contacts.length || 0}
                  unit=""
                />
                <KpiCard
                  label="Fidelity"
                  value={missionStore.state.runData?.manifest.fidelity || '-'}
                  unit=""
                />
              </div>
            </section>

            <section class="alerts-section">
              <h3 class="section-title">Recent Alerts</h3>
              <AlertsSummary limit={5} />
            </section>
          </div>
        </Show>
      </aside>

      {/* Bottom Timeline */}
      <div class="timeline-area">
        <TimelinePanel />
      </div>

      <style>{`
        .mission-overview {
          display: grid;
          grid-template-columns: 1fr auto;
          grid-template-rows: 1fr auto;
          height: 100%;
          gap: 0;
        }

        .geometry-area {
          grid-column: 1;
          grid-row: 1;
          position: relative;
          overflow: hidden;
        }

        .right-panel {
          grid-column: 2;
          grid-row: 1 / 3;
          width: var(--panel-default-width);
          background: var(--glass-bg);
          border-left: 1px solid var(--neutral-border);
          display: flex;
          flex-direction: column;
          position: relative;
          transition: width var(--transition-normal);
        }

        .right-panel.collapsed {
          width: 40px;
        }

        .collapse-toggle {
          position: absolute;
          left: -12px;
          top: 50%;
          transform: translateY(-50%);
          width: 24px;
          height: 48px;
          border: 1px solid var(--neutral-border);
          border-radius: var(--radius-md);
          background: white;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 14px;
          color: var(--slate-500);
          z-index: 10;
        }

        .collapse-toggle:hover {
          color: var(--slate-700);
          background: var(--slate-50);
        }

        .panel-content {
          flex: 1;
          overflow-y: auto;
          padding: var(--space-4);
        }

        .section-title {
          font-size: var(--text-sm);
          font-weight: var(--font-semibold);
          color: var(--slate-700);
          margin: 0 0 var(--space-3) 0;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .kpi-section {
          margin-bottom: var(--space-6);
        }

        .kpi-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: var(--space-3);
        }

        .alerts-section {
          flex: 1;
        }

        .timeline-area {
          grid-column: 1;
          grid-row: 2;
          height: 120px;
          background: white;
          border-top: 1px solid var(--neutral-border);
        }
      `}</style>
    </div>
  );
};

// KPI Card Component
interface KpiCardProps {
  label: string;
  value: string | number;
  unit: string;
  alert?: boolean;
}

const KpiCard: Component<KpiCardProps> = (props) => {
  return (
    <div class="kpi-card" classList={{ alert: props.alert }}>
      <span class="kpi-label">{props.label}</span>
      <span class="kpi-value">
        {props.value}
        <Show when={props.unit}>
          <span class="kpi-unit">{props.unit}</span>
        </Show>
      </span>
      <style>{`
        .kpi-card {
          padding: var(--space-3);
          background: white;
          border: 1px solid var(--neutral-border);
          border-radius: var(--radius-md);
        }

        .kpi-card.alert {
          border-color: var(--alert-warning);
          background: var(--alert-warning-bg);
        }

        .kpi-label {
          display: block;
          font-size: var(--text-xs);
          color: var(--slate-500);
          margin-bottom: var(--space-1);
        }

        .kpi-value {
          font-size: var(--text-lg);
          font-weight: var(--font-semibold);
          color: var(--slate-800);
          font-family: var(--font-mono);
        }

        .kpi-unit {
          font-size: var(--text-xs);
          color: var(--slate-500);
          margin-left: var(--space-1);
        }
      `}</style>
    </div>
  );
};

function formatElapsedTime(hours: number): string {
  if (hours < 1) {
    return `${Math.round(hours * 60)}m`;
  }
  return `${hours.toFixed(1)}h`;
}
