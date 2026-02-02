/**
 * Time Store - Temporal State Management
 * Manages simulation time, playback, and temporal navigation
 */

import { createSignal, createEffect, onCleanup } from 'solid-js';
import type { TimeRange, PlaybackSpeed } from '@/types';

// ============================================
// TIME STATE
// ============================================

const [currentTime, setCurrentTime] = createSignal<Date>(new Date());
const [timeRange, setTimeRange] = createSignal<TimeRange>({
  start: new Date(),
  end: new Date(),
});
const [isPlaying, setIsPlaying] = createSignal(false);
const [playbackSpeed, setPlaybackSpeedInternal] = createSignal<PlaybackSpeed>(60);

// Animation frame reference
let animationFrameId: number | null = null;
let lastFrameTime: number = 0;

// ============================================
// PLAYBACK CONTROL
// ============================================

function startPlayback(): void {
  if (isPlaying()) return;

  setIsPlaying(true);
  lastFrameTime = performance.now();
  animationFrameId = requestAnimationFrame(updatePlayback);
}

function stopPlayback(): void {
  setIsPlaying(false);
  if (animationFrameId !== null) {
    cancelAnimationFrame(animationFrameId);
    animationFrameId = null;
  }
}

function togglePlayback(): void {
  if (isPlaying()) {
    stopPlayback();
  } else {
    startPlayback();
  }
}

function updatePlayback(frameTime: number): void {
  if (!isPlaying()) return;

  const deltaMs = frameTime - lastFrameTime;
  lastFrameTime = frameTime;

  // Apply playback speed multiplier
  const simulatedDeltaMs = deltaMs * playbackSpeed();

  const newTime = new Date(currentTime().getTime() + simulatedDeltaMs);
  const range = timeRange();

  // Clamp to time range
  if (newTime >= range.end) {
    setCurrentTime(range.end);
    stopPlayback();
    return;
  }

  setCurrentTime(newTime);
  animationFrameId = requestAnimationFrame(updatePlayback);
}

// ============================================
// TIME NAVIGATION
// ============================================

function jumpToTime(time: Date): void {
  const range = timeRange();
  const clampedTime = new Date(
    Math.max(range.start.getTime(), Math.min(range.end.getTime(), time.getTime()))
  );
  setCurrentTime(clampedTime);
}

function jumpToStart(): void {
  setCurrentTime(timeRange().start);
}

function jumpToEnd(): void {
  setCurrentTime(timeRange().end);
}

function stepForward(seconds: number = 60): void {
  const newTime = new Date(currentTime().getTime() + seconds * 1000);
  jumpToTime(newTime);
}

function stepBackward(seconds: number = 60): void {
  const newTime = new Date(currentTime().getTime() - seconds * 1000);
  jumpToTime(newTime);
}

// ============================================
// SPEED CONTROL
// ============================================

function setPlaybackSpeed(speed: PlaybackSpeed): void {
  setPlaybackSpeedInternal(speed);
}

function cycleSpeed(): void {
  const speeds: PlaybackSpeed[] = [1, 10, 60, 300, 1000];
  const currentIndex = speeds.indexOf(playbackSpeed());
  const nextIndex = (currentIndex + 1) % speeds.length;
  setPlaybackSpeedInternal(speeds[nextIndex]);
}

// ============================================
// TIME RANGE MANAGEMENT
// ============================================

function initializeTimeRange(start: Date | string, end: Date | string): void {
  const startDate = start instanceof Date ? start : new Date(start);
  const endDate = end instanceof Date ? end : new Date(end);

  setTimeRange({ start: startDate, end: endDate });
  setCurrentTime(startDate);
}

// ============================================
// UTILITIES
// ============================================

function formatTime(date: Date): string {
  return date.toISOString().slice(0, 19).replace('T', ' ') + ' UTC';
}

function formatTimeShort(date: Date): string {
  return date.toISOString().slice(11, 19);
}

function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);

  if (hours > 0) {
    return `${hours}h ${minutes}m ${secs}s`;
  } else if (minutes > 0) {
    return `${minutes}m ${secs}s`;
  } else {
    return `${secs}s`;
  }
}

function getProgress(): number {
  const range = timeRange();
  const total = range.end.getTime() - range.start.getTime();
  if (total === 0) return 0;

  const elapsed = currentTime().getTime() - range.start.getTime();
  return Math.max(0, Math.min(1, elapsed / total));
}

function getElapsedSeconds(): number {
  const range = timeRange();
  return (currentTime().getTime() - range.start.getTime()) / 1000;
}

function getTotalSeconds(): number {
  const range = timeRange();
  return (range.end.getTime() - range.start.getTime()) / 1000;
}

// ============================================
// CLEANUP
// ============================================

function cleanup(): void {
  stopPlayback();
}

// ============================================
// STORE EXPORT
// ============================================

export const timeStore = {
  // Signals
  currentTime,
  timeRange,
  isPlaying,
  playbackSpeed,

  // Setters
  setCurrentTime,
  setTimeRange,
  initializeTimeRange,

  // Playback control
  startPlayback,
  stopPlayback,
  togglePlayback,
  setPlaybackSpeed,
  cycleSpeed,

  // Navigation
  jumpToTime,
  jumpToStart,
  jumpToEnd,
  stepForward,
  stepBackward,

  // Utilities
  formatTime,
  formatTimeShort,
  formatDuration,
  getProgress,
  getElapsedSeconds,
  getTotalSeconds,

  // Cleanup
  cleanup,
};

export default timeStore;
