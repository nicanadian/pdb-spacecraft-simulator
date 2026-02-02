/**
 * Payload Operations Workspace
 * Targeting, imaging, and downlink management
 */

import { Component, For, Show } from 'solid-js';
import { GeometryView } from '@/components/geometry/GeometryView';
import { TimelinePanel } from '@/components/timeline/TimelinePanel';
import { missionStore } from '@/stores/missionStore';

export const PayloadOperations: Component = () => {
  const contacts = () => missionStore.state.runData?.contacts || [];

  return (
    <div class="payload-workspace">
      {/* Left: Targeting Queue */}
      <aside class="targeting-panel glass-sidebar">
        <div class="panel-header">
          <h3>Targeting Queue</h3>
          <button class="btn btn-ghost btn-sm">+ Add</button>
        </div>

        <div class="panel-content">
          <div class="empty-state">
            <p>No imaging targets scheduled</p>
          </div>
        </div>
      </aside>

      {/* Center: Geometry with sensor footprint */}
      <div class="geometry-area">
        <GeometryView showSensorFootprint={true} />
      </div>

      {/* Right: Storage & Downlink */}
      <aside class="storage-panel glass-sidebar">
        <div class="panel-header">
          <h3>Storage Status</h3>
        </div>

        <div class="panel-content">
          <div class="storage-meter">
            <div class="meter-header">
              <span class="meter-label">Onboard Storage</span>
              <span class="meter-value font-mono">-- / -- GB</span>
            </div>
            <div class="meter-bar">
              <div class="meter-fill" style={{ width: '0%' }} />
            </div>
          </div>

          <div class="section-divider" />

          <div class="contacts-section">
            <h4>Upcoming Contacts</h4>
            <Show
              when={contacts().length > 0}
              fallback={<p class="no-contacts">No upcoming contacts</p>}
            >
              <div class="contacts-list">
                <For each={contacts().slice(0, 5)}>
                  {(contact) => (
                    <div class="contact-item">
                      <span class="contact-station">{contact.stationName}</span>
                      <span class="contact-time font-mono">
                        {formatContactTime(contact.aos)}
                      </span>
                      <span class="contact-duration font-mono">
                        {Math.round(contact.duration / 60)}m
                      </span>
                    </div>
                  )}
                </For>
              </div>
            </Show>
          </div>
        </div>
      </aside>

      {/* Bottom: Timeline with contact windows */}
      <div class="timeline-area">
        <TimelinePanel showContactWindows={true} />
      </div>

      <style>{`
        .payload-workspace {
          display: grid;
          grid-template-columns: var(--panel-min-width) 1fr var(--panel-default-width);
          grid-template-rows: 1fr 120px;
          height: 100%;
        }

        .targeting-panel {
          grid-column: 1;
          grid-row: 1 / 3;
          background: var(--glass-bg);
          border-right: 1px solid var(--neutral-border);
          display: flex;
          flex-direction: column;
        }

        .geometry-area {
          grid-column: 2;
          grid-row: 1;
          position: relative;
        }

        .storage-panel {
          grid-column: 3;
          grid-row: 1 / 3;
          background: var(--glass-bg);
          border-left: 1px solid var(--neutral-border);
          display: flex;
          flex-direction: column;
        }

        .panel-header {
          padding: var(--space-4);
          border-bottom: 1px solid var(--neutral-border);
          display: flex;
          align-items: center;
          justify-content: space-between;
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
          overflow-y: auto;
        }

        .empty-state {
          display: flex;
          align-items: center;
          justify-content: center;
          height: 100%;
          color: var(--slate-500);
          font-size: var(--text-sm);
        }

        .storage-meter {
          margin-bottom: var(--space-4);
        }

        .meter-header {
          display: flex;
          justify-content: space-between;
          margin-bottom: var(--space-2);
        }

        .meter-label {
          font-size: var(--text-xs);
          color: var(--slate-500);
        }

        .meter-value {
          font-size: var(--text-xs);
          color: var(--slate-700);
        }

        .meter-bar {
          height: 8px;
          background: var(--slate-200);
          border-radius: var(--radius-full);
          overflow: hidden;
        }

        .meter-fill {
          height: 100%;
          background: var(--electric-teal);
          border-radius: var(--radius-full);
          transition: width var(--transition-normal);
        }

        .section-divider {
          height: 1px;
          background: var(--neutral-border);
          margin: var(--space-4) 0;
        }

        .contacts-section h4 {
          font-size: var(--text-xs);
          font-weight: var(--font-semibold);
          color: var(--slate-600);
          margin: 0 0 var(--space-3) 0;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .no-contacts {
          font-size: var(--text-sm);
          color: var(--slate-500);
        }

        .contacts-list {
          display: flex;
          flex-direction: column;
          gap: var(--space-2);
        }

        .contact-item {
          display: grid;
          grid-template-columns: 1fr auto auto;
          gap: var(--space-2);
          padding: var(--space-2);
          background: white;
          border: 1px solid var(--neutral-border);
          border-radius: var(--radius-sm);
          font-size: var(--text-xs);
        }

        .contact-station {
          color: var(--slate-700);
          font-weight: var(--font-medium);
        }

        .contact-time {
          color: var(--slate-500);
        }

        .contact-duration {
          color: var(--electric-teal);
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

function formatContactTime(date: Date): string {
  return date.toISOString().slice(11, 16);
}
