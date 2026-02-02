/**
 * Compare summary panel for displaying run differences.
 */
import { formatDiff } from '../compare/loader.js';

/**
 * Create and render the compare summary panel.
 *
 * @param {Object} compareData - Comparison data
 * @returns {HTMLElement} Panel element
 */
export function createCompareSummaryPanel(compareData) {
    const panel = document.createElement('div');
    panel.className = 'compare-panel';
    panel.id = 'compareSummary';

    const diff = formatDiff(compareData.diff);

    panel.innerHTML = `
        <div class="compare-header">
            <h3>Comparison Summary</h3>
        </div>
        <div class="compare-content">
            <div class="compare-runs">
                <div class="run-info run-a">
                    <span class="run-label">Run A:</span>
                    <span class="run-id">${compareData.runA?.manifest?.run_id || 'Unknown'}</span>
                    <span class="run-fidelity">${compareData.runA?.manifest?.fidelity || '--'}</span>
                </div>
                <div class="run-info run-b">
                    <span class="run-label">Run B:</span>
                    <span class="run-id">${compareData.runB?.manifest?.run_id || 'Unknown'}</span>
                    <span class="run-fidelity">${compareData.runB?.manifest?.fidelity || '--'}</span>
                </div>
            </div>

            ${diff ? renderDiffMetrics(diff) : '<p>No diff data available</p>'}

            ${diff?.warnings?.length ? renderWarnings(diff.warnings) : ''}
        </div>
    `;

    return panel;
}

/**
 * Render diff metrics section.
 *
 * @param {Object} diff - Formatted diff data
 * @returns {string} HTML string
 */
function renderDiffMetrics(diff) {
    return `
        <div class="diff-section">
            <h4>Position Difference</h4>
            <div class="metric-row">
                <span class="metric-label">RMSE:</span>
                <span class="metric-value">${diff.position.rmse} ${diff.position.unit}</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Maximum:</span>
                <span class="metric-value">${diff.position.max} ${diff.position.unit}</span>
            </div>
        </div>

        <div class="diff-section">
            <h4>Contact Timing</h4>
            <div class="metric-row">
                <span class="metric-label">RMSE:</span>
                <span class="metric-value">${diff.contacts.timingRmse} s</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Differences:</span>
                <span class="metric-value">${diff.contacts.diffs.length} contacts</span>
            </div>
        </div>

        <div class="diff-section">
            <h4>State Differences</h4>
            <div class="metric-row">
                <span class="metric-label">SOC RMSE:</span>
                <span class="metric-value">${diff.state.socRmse}%</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Storage RMSE:</span>
                <span class="metric-value">${diff.state.storageRmse} GB</span>
            </div>
        </div>
    `;
}

/**
 * Render warnings section.
 *
 * @param {Array} warnings - Warning messages
 * @returns {string} HTML string
 */
function renderWarnings(warnings) {
    return `
        <div class="diff-warnings">
            <h4>Warnings</h4>
            <ul>
                ${warnings.map(w => `<li>${w}</li>`).join('')}
            </ul>
        </div>
    `;
}

/**
 * Add compare summary styles to the page.
 */
export function addCompareSummaryStyles() {
    const style = document.createElement('style');
    style.textContent = `
        .compare-panel {
            background: #16213e;
            border-radius: 8px;
            margin: 10px;
            overflow: hidden;
        }

        .compare-header {
            background: #1a1a2e;
            padding: 12px 16px;
        }

        .compare-header h3 {
            margin: 0;
            font-size: 14px;
            font-weight: 500;
        }

        .compare-content {
            padding: 16px;
        }

        .compare-runs {
            display: flex;
            gap: 20px;
            margin-bottom: 20px;
        }

        .run-info {
            flex: 1;
            padding: 10px;
            border-radius: 4px;
        }

        .run-a {
            background: rgba(0, 255, 255, 0.1);
            border-left: 3px solid cyan;
        }

        .run-b {
            background: rgba(255, 0, 255, 0.1);
            border-left: 3px solid magenta;
        }

        .run-label {
            font-size: 11px;
            color: #8888aa;
            display: block;
        }

        .run-id {
            font-size: 13px;
            display: block;
            margin-top: 4px;
        }

        .run-fidelity {
            font-size: 11px;
            color: #8888aa;
        }

        .diff-section {
            margin-bottom: 16px;
        }

        .diff-section h4 {
            font-size: 12px;
            color: #8888aa;
            margin: 0 0 8px 0;
            text-transform: uppercase;
        }

        .metric-row {
            display: flex;
            justify-content: space-between;
            padding: 4px 0;
            font-size: 13px;
        }

        .metric-label {
            color: #aaa;
        }

        .metric-value {
            font-family: monospace;
        }

        .diff-warnings {
            margin-top: 16px;
            padding: 12px;
            background: rgba(243, 156, 18, 0.1);
            border-radius: 4px;
            border-left: 3px solid #f39c12;
        }

        .diff-warnings h4 {
            color: #f39c12;
            margin: 0 0 8px 0;
            font-size: 12px;
        }

        .diff-warnings ul {
            margin: 0;
            padding-left: 20px;
            font-size: 12px;
        }

        .diff-warnings li {
            margin-bottom: 4px;
        }
    `;
    document.head.appendChild(style);
}
