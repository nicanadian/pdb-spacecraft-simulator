/**
 * Data loader for simulation run outputs.
 */
import { loadCZML, configureClockRange } from './viewer.js';

/**
 * Load all data for a simulation run.
 *
 * @param {string} basePath - Base path to run directory
 * @returns {Promise<Object>} Run data object
 */
export async function loadRunData(basePath) {
    const data = {
        manifest: null,
        events: [],
        contacts: {},
        eclipses: [],
        czmlDataSource: null,
    };

    // Normalize path
    if (!basePath.endsWith('/')) {
        basePath += '/';
    }

    // Try viz subdirectory first
    let manifestPath = `${basePath}viz/run_manifest.json`;
    let czmlPath = `${basePath}viz/scene.czml`;
    let eventsPath = `${basePath}viz/events.json`;

    // Load manifest
    try {
        const resp = await fetch(manifestPath);
        if (resp.ok) {
            data.manifest = await resp.json();
        } else {
            // Try root level
            manifestPath = `${basePath}run_manifest.json`;
            const resp2 = await fetch(manifestPath);
            if (resp2.ok) {
                data.manifest = await resp2.json();
            }
        }
    } catch (e) {
        console.warn('Could not load manifest:', e);
    }

    // Load events
    try {
        const resp = await fetch(eventsPath);
        if (resp.ok) {
            data.events = await resp.json();
        } else {
            // Try root level
            const resp2 = await fetch(`${basePath}events.json`);
            if (resp2.ok) {
                data.events = await resp2.json();
            }
        }
    } catch (e) {
        console.warn('Could not load events:', e);
    }

    // Load access windows
    try {
        const resp = await fetch(`${basePath}access_windows.json`);
        if (resp.ok) {
            data.contacts = await resp.json();
        }
    } catch (e) {
        console.warn('Could not load access windows:', e);
    }

    // Load eclipses
    try {
        const resp = await fetch(`${basePath}eclipse_windows.json`);
        if (resp.ok) {
            data.eclipses = await resp.json();
        }
    } catch (e) {
        console.warn('Could not load eclipse windows:', e);
    }

    console.log('Run data loaded:', {
        hasManifest: !!data.manifest,
        eventCount: data.events.length,
        stationCount: Object.keys(data.contacts).length,
        eclipseCount: data.eclipses.length,
    });

    return data;
}

/**
 * Load CZML into viewer and configure clock.
 *
 * @param {Cesium.Viewer} viewer - The viewer
 * @param {string} basePath - Base path to run
 * @param {Object} runData - Loaded run data
 */
export async function loadVisualization(viewer, basePath, runData) {
    // Normalize path
    if (!basePath.endsWith('/')) {
        basePath += '/';
    }

    // Load CZML
    let czmlPath = `${basePath}viz/scene.czml`;
    try {
        runData.czmlDataSource = await loadCZML(viewer, czmlPath);
    } catch (e) {
        console.warn('Could not load CZML from viz/, trying root');
        try {
            czmlPath = `${basePath}scene.czml`;
            runData.czmlDataSource = await loadCZML(viewer, czmlPath);
        } catch (e2) {
            console.error('Could not load CZML:', e2);
        }
    }

    // Configure clock from manifest
    if (runData.manifest?.time_range) {
        const tr = runData.manifest.time_range;
        configureClockRange(viewer, tr.start, tr.end, 60);
    }
}

/**
 * Format a contact window for display.
 *
 * @param {Object} contact - Contact window object
 * @param {string} stationId - Station ID
 * @returns {Object} Formatted contact
 */
export function formatContact(contact, stationId) {
    const start = new Date(contact.start_time);
    const end = new Date(contact.end_time);
    const duration = (end - start) / 1000;

    return {
        stationId,
        startTime: start,
        endTime: end,
        durationMin: (duration / 60).toFixed(1),
        maxElevation: contact.max_elevation_deg?.toFixed(1) || '--',
    };
}

/**
 * Get all contacts as a flat list.
 *
 * @param {Object} contactsData - Contacts by station
 * @returns {Array} Flat list of contacts
 */
export function getAllContacts(contactsData) {
    const contacts = [];

    for (const [stationId, windows] of Object.entries(contactsData)) {
        for (const window of windows) {
            contacts.push(formatContact(window, stationId));
        }
    }

    // Sort by start time
    contacts.sort((a, b) => a.startTime - b.startTime);

    return contacts;
}
