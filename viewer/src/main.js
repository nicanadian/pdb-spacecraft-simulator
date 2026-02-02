/**
 * Main entry point for the spacecraft viewer application.
 */
import { initViewer } from './viewer.js';
import { loadRunData, loadVisualization } from './loader.js';
import { setupTimeline } from './controls/timeline.js';
import { setupEventPanel } from './panels/events.js';

// Global viewer instance
let viewer = null;
let runData = null;

/**
 * Initialize the application.
 */
async function init() {
    console.log('Initializing spacecraft viewer...');

    try {
        // Initialize Cesium viewer
        viewer = await initViewer('cesiumContainer');

        // Get run path from URL params or use default
        const urlParams = new URLSearchParams(window.location.search);
        const runPath = urlParams.get('run') || '.';

        // Load run data
        runData = await loadRunData(runPath);
        updateRunInfo(runData);

        // Load CZML visualization
        await loadVisualization(viewer, runPath, runData);

        // Set up timeline controls
        setupTimeline(viewer, runData);

        // Set up event panel
        setupEventPanel(viewer, runData);

        // Hide loading indicator
        document.getElementById('loading').style.display = 'none';

        console.log('Viewer initialized successfully');

    } catch (error) {
        console.error('Failed to initialize viewer:', error);
        document.getElementById('loading').textContent =
            `Error: ${error.message}`;
    }
}

/**
 * Update the run info display in the header.
 */
function updateRunInfo(data) {
    const infoEl = document.getElementById('runInfo');
    if (data.manifest) {
        const m = data.manifest;
        infoEl.textContent = `${m.plan_id} | ${m.fidelity} | ${m.duration_hours?.toFixed(1) || '--'}h`;
    } else {
        infoEl.textContent = 'Run data loaded';
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}

// Export for debugging
window.getViewer = () => viewer;
window.getRunData = () => runData;
