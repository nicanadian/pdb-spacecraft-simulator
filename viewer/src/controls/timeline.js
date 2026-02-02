/**
 * Timeline controls for playback.
 */
import * as Cesium from 'cesium';

let isPlaying = false;
let tickHandler = null;

/**
 * Set up timeline controls.
 *
 * @param {Cesium.Viewer} viewer - The viewer instance
 * @param {Object} runData - Loaded run data
 */
export function setupTimeline(viewer, runData) {
    const playPauseBtn = document.getElementById('playPauseBtn');
    const resetBtn = document.getElementById('resetBtn');
    const speedSelect = document.getElementById('speedSelect');
    const timeDisplay = document.getElementById('timeDisplay');

    // Play/pause button
    playPauseBtn.addEventListener('click', () => {
        isPlaying = !isPlaying;
        viewer.clock.shouldAnimate = isPlaying;
        playPauseBtn.textContent = isPlaying ? 'Pause' : 'Play';
    });

    // Reset button
    resetBtn.addEventListener('click', () => {
        viewer.clock.currentTime = viewer.clock.startTime.clone();
        isPlaying = false;
        viewer.clock.shouldAnimate = false;
        playPauseBtn.textContent = 'Play';
    });

    // Speed control
    speedSelect.addEventListener('change', () => {
        viewer.clock.multiplier = parseInt(speedSelect.value, 10);
    });

    // Time display update
    tickHandler = viewer.clock.onTick.addEventListener((clock) => {
        const time = Cesium.JulianDate.toDate(clock.currentTime);
        timeDisplay.textContent = formatTime(time);
    });

    // Initial state
    viewer.clock.shouldAnimate = false;
    viewer.clock.multiplier = 60;
}

/**
 * Format a date for display.
 *
 * @param {Date} date - Date to format
 * @returns {string} Formatted time string
 */
function formatTime(date) {
    const pad = (n) => n.toString().padStart(2, '0');

    const year = date.getUTCFullYear();
    const month = pad(date.getUTCMonth() + 1);
    const day = pad(date.getUTCDate());
    const hours = pad(date.getUTCHours());
    const minutes = pad(date.getUTCMinutes());
    const seconds = pad(date.getUTCSeconds());

    return `${year}-${month}-${day} ${hours}:${minutes}:${seconds} UTC`;
}

/**
 * Jump to a specific time.
 *
 * @param {Cesium.Viewer} viewer - The viewer
 * @param {Date|string} time - Time to jump to
 */
export function jumpToTime(viewer, time) {
    if (typeof time === 'string') {
        time = new Date(time);
    }

    const julianTime = Cesium.JulianDate.fromDate(time);
    viewer.clock.currentTime = julianTime;
}

/**
 * Clean up timeline handlers.
 *
 * @param {Cesium.Viewer} viewer - The viewer
 */
export function cleanupTimeline(viewer) {
    if (tickHandler) {
        viewer.clock.onTick.removeEventListener(tickHandler);
        tickHandler = null;
    }
}
