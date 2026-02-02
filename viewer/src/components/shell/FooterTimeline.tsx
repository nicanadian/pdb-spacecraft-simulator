/**
 * Footer Timeline - Playback controls and time display
 */

import { Component, createSignal, createEffect } from 'solid-js';
import { timeStore } from '@/stores/timeStore';
import type { PlaybackSpeed } from '@/types';

export const FooterTimeline: Component = () => {
  const speeds: PlaybackSpeed[] = [1, 10, 60, 300, 1000];

  const handleProgressClick = (e: MouseEvent) => {
    const target = e.currentTarget as HTMLElement;
    const rect = target.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const progress = x / rect.width;

    const range = timeStore.timeRange();
    const totalMs = range.end.getTime() - range.start.getTime();
    const newTime = new Date(range.start.getTime() + totalMs * progress);
    timeStore.jumpToTime(newTime);
  };

  return (
    <footer class="footer-timeline">
      <div class="playback-controls">
        <button
          class="btn btn-icon btn-ghost"
          onClick={() => timeStore.jumpToStart()}
          title="Jump to start"
        >
          {'\u23EE'}
        </button>
        <button
          class="btn btn-icon btn-ghost"
          onClick={() => timeStore.stepBackward(60)}
          title="Step back 1 minute"
        >
          {'\u23EA'}
        </button>
        <button
          class="play-button"
          classList={{ playing: timeStore.isPlaying() }}
          onClick={() => timeStore.togglePlayback()}
        >
          {timeStore.isPlaying() ? '\u23F8' : '\u25B6'}
        </button>
        <button
          class="btn btn-icon btn-ghost"
          onClick={() => timeStore.stepForward(60)}
          title="Step forward 1 minute"
        >
          {'\u23E9'}
        </button>
        <button
          class="btn btn-icon btn-ghost"
          onClick={() => timeStore.jumpToEnd()}
          title="Jump to end"
        >
          {'\u23ED'}
        </button>
      </div>

      <div class="timeline-track" onClick={handleProgressClick}>
        <div class="timeline-background" />
        <div
          class="timeline-progress"
          style={{ width: `${timeStore.getProgress() * 100}%` }}
        />
        <div
          class="timeline-handle"
          style={{ left: `${timeStore.getProgress() * 100}%` }}
        />
      </div>

      <div class="time-display">
        <span class="current-time font-mono">
          {timeStore.formatTime(timeStore.currentTime())}
        </span>
        <span class="time-separator">/</span>
        <span class="elapsed-time font-mono text-slate-500">
          {timeStore.formatDuration(timeStore.getElapsedSeconds())}
        </span>
      </div>

      <div class="speed-control">
        <label class="speed-label">Speed:</label>
        <select
          class="select"
          value={timeStore.playbackSpeed()}
          onChange={(e) =>
            timeStore.setPlaybackSpeed(Number(e.target.value) as PlaybackSpeed)
          }
        >
          {speeds.map((speed) => (
            <option value={speed}>{speed}x</option>
          ))}
        </select>
      </div>

      <style>{`
        .footer-timeline {
          height: var(--footer-height);
          min-height: var(--footer-height);
          display: flex;
          align-items: center;
          gap: var(--space-4);
          padding: 0 var(--space-4);
          background: white;
          border-top: 1px solid var(--neutral-border);
        }

        .playback-controls {
          display: flex;
          align-items: center;
          gap: var(--space-1);
        }

        .play-button {
          width: 40px;
          height: 40px;
          border-radius: 50%;
          border: none;
          background: var(--electric-teal);
          color: white;
          font-size: 16px;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: all var(--transition-fast);
        }

        .play-button:hover {
          background: #0284a8;
          transform: scale(1.05);
        }

        .play-button.playing {
          background: var(--slate-600);
        }

        .timeline-track {
          flex: 1;
          height: 8px;
          background: var(--slate-200);
          border-radius: var(--radius-full);
          position: relative;
          cursor: pointer;
        }

        .timeline-background {
          position: absolute;
          inset: 0;
          border-radius: var(--radius-full);
        }

        .timeline-progress {
          position: absolute;
          left: 0;
          top: 0;
          bottom: 0;
          background: var(--electric-teal);
          border-radius: var(--radius-full);
          transition: width 0.1s linear;
        }

        .timeline-handle {
          position: absolute;
          top: 50%;
          transform: translate(-50%, -50%);
          width: 16px;
          height: 16px;
          background: white;
          border: 2px solid var(--electric-teal);
          border-radius: 50%;
          box-shadow: var(--shadow-sm);
          transition: left 0.1s linear;
        }

        .timeline-handle:hover {
          transform: translate(-50%, -50%) scale(1.2);
        }

        .time-display {
          display: flex;
          align-items: center;
          gap: var(--space-2);
          min-width: 280px;
        }

        .current-time {
          font-size: var(--text-sm);
          color: var(--slate-800);
        }

        .time-separator {
          color: var(--slate-400);
        }

        .elapsed-time {
          font-size: var(--text-xs);
        }

        .speed-control {
          display: flex;
          align-items: center;
          gap: var(--space-2);
        }

        .speed-label {
          font-size: var(--text-xs);
          color: var(--slate-500);
        }

        .speed-control .select {
          width: 80px;
        }
      `}</style>
    </footer>
  );
};
