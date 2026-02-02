/**
 * Loader for compare mode with two runs.
 */

/**
 * Load data for two runs for comparison.
 *
 * @param {string} runAPath - Path to first run
 * @param {string} runBPath - Path to second run
 * @returns {Promise<Object>} Combined comparison data
 */
export async function loadCompareData(runAPath, runBPath) {
    const data = {
        runA: null,
        runB: null,
        diff: null,
        compareCzml: null,
    };

    // Normalize paths
    if (!runAPath.endsWith('/')) runAPath += '/';
    if (!runBPath.endsWith('/')) runBPath += '/';

    // Load manifests
    try {
        const respA = await fetch(`${runAPath}run_manifest.json`);
        if (respA.ok) data.runA = { manifest: await respA.json(), path: runAPath };
    } catch (e) {
        console.warn('Could not load run A manifest');
    }

    try {
        const respB = await fetch(`${runBPath}run_manifest.json`);
        if (respB.ok) data.runB = { manifest: await respB.json(), path: runBPath };
    } catch (e) {
        console.warn('Could not load run B manifest');
    }

    // Load diff data
    const comparePath = runAPath.replace(/[^\/]+\/?$/, 'compare/');
    try {
        const respDiff = await fetch(`${comparePath}diff.json`);
        if (respDiff.ok) data.diff = await respDiff.json();
    } catch (e) {
        console.warn('Could not load diff data');
    }

    return data;
}

/**
 * Load comparison CZML into viewer.
 *
 * @param {Cesium.Viewer} viewer - The viewer
 * @param {string} comparePath - Path to compare directory
 * @returns {Promise} Loaded data source
 */
export async function loadCompareCzml(viewer, comparePath) {
    const czmlUrl = `${comparePath}compare.czml`;

    try {
        const Cesium = await import('cesium');
        const dataSource = await Cesium.CzmlDataSource.load(czmlUrl);
        await viewer.dataSources.add(dataSource);
        return dataSource;
    } catch (e) {
        console.error('Could not load compare CZML:', e);
        throw e;
    }
}

/**
 * Format diff data for display.
 *
 * @param {Object} diff - Diff data
 * @returns {Object} Formatted diff
 */
export function formatDiff(diff) {
    if (!diff) return null;

    return {
        position: {
            rmse: diff.position?.rmse_km?.toFixed(3) || '--',
            max: diff.position?.max_diff_km?.toFixed(3) || '--',
            unit: 'km',
        },
        contacts: {
            timingRmse: diff.contacts?.timing_rmse_s?.toFixed(1) || '--',
            diffs: diff.contacts?.diffs || [],
        },
        state: {
            socRmse: (diff.state?.soc_rmse * 100)?.toFixed(1) || '--',
            storageRmse: diff.state?.storage_rmse_gb?.toFixed(2) || '--',
        },
        comparable: diff.comparable ?? true,
        warnings: diff.warnings || [],
    };
}
