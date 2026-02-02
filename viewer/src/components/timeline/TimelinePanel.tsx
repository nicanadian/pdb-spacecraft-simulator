/**
 * Timeline Panel - Multi-lane visualization with semantic zoom
 * Core component for temporal navigation and activity visualization
 */

import { Component, For, Show, createSignal, createMemo } from 'solid-js';
import { timeStore } from '@/stores/timeStore';
import { selectionStore } from '@/stores/selectionStore';
import { missionStore } from '@/stores/missionStore';
import type { ContactWindow, ConstraintEvent } from '@/types';

interface TimelinePanelProps {
  showGhostTrack?: boolean;
  showAltitudeProfile?: boolean;
  showContactWindows?: boolean;
}

export const TimelinePanel: Component<TimelinePanelProps> = (props) => {
  const [zoomLevel, setZoomLevel] = createSignal(1);
  let trackRef: HTMLDivElement | undefined;

  const timeRange = () => timeStore.timeRange();
  const currentTime = () => timeStore.currentTime();

  const contacts = createMemo(() =>
    missionStore.state.runData?.contacts || []
  );

  const events = createMemo(() =>
    missionStore.state.runData?.events || []
  );

  // Calculate position for a given time
  const getTimePosition = (time: Date): number => {
    const range = timeRange();
    const total = range.end.getTime() - range.start.getTime();
    if (total === 0) return 0;
    const elapsed = time.getTime() - range.start.getTime();
    return (elapsed / total) * 100;
  };

  // Handle click on timeline track
  const handleTrackClick = (e: MouseEvent) => {
    if (!trackRef) return;
    const rect = trackRef.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const progress = x / rect.width;

    const range = timeRange();
    const totalMs = range.end.getTime() - range.start.getTime();
    const newTime = new Date(range.start.getTime() + totalMs * progress);
    timeStore.jumpToTime(newTime);
  };

  // Handle contact click
  const handleContactClick = (contact: ContactWindow) => {
    selectionStore.selectContact(contact);
  };

  // Handle event click
  const handleEventClick = (event: ConstraintEvent) => {
    timeStore.jumpToTime(event.timestamp);
  };

  return (
    <div class="timeline-panel">
      {/* Timeline Header */}
      <div class="timeline-header">
        <div class="time-markers">
          <span class="time-marker font-mono">
            {formatTimeLabel(timeRange().start)}
          </span>
          <span class="time-marker font-mono current">
            {formatTimeLabel(currentTime())}
          </span>
          <span class="time-marker font-mono">
            {formatTimeLabel(timeRange().end)}
          </span>
        </div>
      </div>

      {/* Timeline Lanes */}
      <div class="timeline-lanes" ref={trackRef} onClick={handleTrackClick}>
        {/* Current Time Indicator */}
        <div
          class="time-cursor"
          style={{ left: `${timeStore.getProgress() * 100}%` }}
        />

        {/* Contact Windows Lane */}
        <Show when={props.showContactWindows !== false}>
          <div class="lane contacts-lane">
            <span class="lane-label">Contacts</span>
            <div class="lane-track">
              <For each={contacts()}>
                {(contact) => (
                  <div
                    class="contact-block"
                    style={{
                      left: `${getTimePosition(contact.aos)}%`,
                      width: `${getTimePosition(contact.los) - getTimePosition(contact.aos)}%`,
                    }}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleContactClick(contact);
                    }}
                    title={`${contact.stationName}: ${Math.round(contact.duration / 60)}min`}
                  />
                )}
              </For>
            </div>
          </div>
        </Show>

        {/* Events Lane */}
        <div class="lane events-lane">
          <span class="lane-label">Events</span>
          <div class="lane-track">
            <For each={events()}>
              {(event) => (
                <div
                  class="event-marker"
                  classList={{
                    info: event.severity === 'info',
                    warning: event.severity === 'warning',
                    failure: event.severity === 'failure',
                  }}
                  style={{ left: `${getTimePosition(event.timestamp)}%` }}
                  onClick={(e) => {
                    e.stopPropagation();
                    handleEventClick(event);
                  }}
                  title={event.message}
                />
              )}
            </For>
          </div>
        </div>

        {/* Ghost Track (for branching mode) */}
        <Show when={props.showGhostTrack}>
          <div class="lane ghost-lane">
            <span class="lane-label">What-If</span>
            <div class="lane-track ghost">
              <div class="ghost-path dashed-path" />
            </div>
          </div>
        </Show>
      </div>

      <style>{`
        .timeline-panel {
          height: 100%;
          display: flex;
          flex-direction: column;
          padding: var(--space-2) var(--space-4);
        }

        .timeline-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: var(--space-2);
        }

        .time-markers {
          display: flex;
          justify-content: space-between;
          width: 100%;
          padding-left: 60px;
        }

        .time-marker {
          font-size: var(--text-xs);
          color: var(--slate-500);
        }

        .time-marker.current {
          color: var(--electric-teal);
          font-weight: var(--font-medium);
        }

        .timeline-lanes {
          flex: 1;
          display: flex;
          flex-direction: column;
          gap: var(--space-1);
          position: relative;
          cursor: pointer;
        }

        .time-cursor {
          position: absolute;
          top: 0;
          bottom: 0;
          width: 2px;
          background: var(--electric-teal);
          z-index: 10;
          pointer-events: none;
        }

        .time-cursor::before {
          content: '';
          position: absolute;
          top: -4px;
          left: -4px;
          width: 10px;
          height: 10px;
          background: var(--electric-teal);
          border-radius: 50%;
        }

        .lane {
          display: flex;
          align-items: center;
          height: 24px;
        }

        .lane-label {
          width: 60px;
          flex-shrink: 0;
          font-size: var(--text-xs);
          color: var(--slate-500);
        }

        .lane-track {
          flex: 1;
          height: 100%;
          background: var(--slate-100);
          border-radius: var(--radius-sm);
          position: relative;
          overflow: hidden;
        }

        .lane-track.ghost {
          background: rgba(8, 145, 178, 0.1);
          border: 1px dashed var(--electric-teal);
        }

        /* Contact Blocks */
        .contact-block {
          position: absolute;
          top: 2px;
          bottom: 2px;
          min-width: 4px;
          background: var(--electric-teal);
          border-radius: 2px;
          opacity: 0.7;
          cursor: pointer;
          transition: opacity var(--transition-fast);
        }

        .contact-block:hover {
          opacity: 1;
        }

        /* Event Markers */
        .event-marker {
          position: absolute;
          top: 50%;
          transform: translate(-50%, -50%);
          width: 8px;
          height: 8px;
          border-radius: 50%;
          cursor: pointer;
          z-index: 5;
        }

        .event-marker.info {
          background: var(--alert-info);
        }

        .event-marker.warning {
          background: var(--alert-warning);
        }

        .event-marker.failure {
          background: var(--alert-failure);
        }

        .event-marker:hover {
          transform: translate(-50%, -50%) scale(1.5);
        }

        /* Ghost Path */
        .ghost-path {
          position: absolute;
          top: 50%;
          left: 0;
          right: 0;
          height: 2px;
          stroke-dasharray: 8 4;
          background: repeating-linear-gradient(
            to right,
            var(--electric-teal),
            var(--electric-teal) 8px,
            transparent 8px,
            transparent 12px
          );
        }
      `}</style>
    </div>
  );
};

function formatTimeLabel(date: Date): string {
  return date.toISOString().slice(11, 19);
}
