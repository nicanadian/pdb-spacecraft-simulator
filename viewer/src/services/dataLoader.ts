/**
 * Data Loader Service
 * Handles loading simulation run data from the filesystem
 */

import type {
  RunData,
  RunManifest,
  ConstraintEvent,
  ContactWindow,
  EclipseWindow,
  Alert,
  AlertSeverity,
} from '@/types';

// ============================================
// DATA LOADING
// ============================================

export async function loadRunData(basePath: string): Promise<RunData> {
  const [manifest, events, contacts, eclipses] = await Promise.all([
    loadManifest(basePath),
    loadEvents(basePath),
    loadContacts(basePath),
    loadEclipses(basePath),
  ]);

  return {
    manifest,
    events,
    contacts,
    eclipses,
    czmlUrl: `${basePath}/viz/scene.czml`,
  };
}

async function loadManifest(basePath: string): Promise<RunManifest> {
  const response = await fetch(`${basePath}/viz/run_manifest.json`);
  if (!response.ok) {
    throw new Error(`Failed to load manifest: ${response.statusText}`);
  }

  const data = await response.json();

  // Extract time range
  const startTime = data.start_time || data.startTime || data.time_range?.start;
  const endTime = data.end_time || data.endTime || data.time_range?.end;

  // Calculate duration if not provided
  let durationHours = data.duration_hours || data.durationHours || 0;
  if (!durationHours && startTime && endTime) {
    const startDate = new Date(startTime);
    const endDate = new Date(endTime);
    durationHours = (endDate.getTime() - startDate.getTime()) / (1000 * 60 * 60);
  }

  return {
    planId: data.plan_id || data.planId || data.run_id || 'unknown',
    fidelity: data.fidelity || 'LOW',
    durationHours,
    startTime,
    endTime,
    spacecraftId: data.spacecraft_id || data.spacecraftId || 'SC-001',
    tle: data.tle,
  };
}

async function loadEvents(basePath: string): Promise<ConstraintEvent[]> {
  try {
    const response = await fetch(`${basePath}/viz/events.json`);
    if (!response.ok) {
      console.warn('Events file not found, using empty list');
      return [];
    }

    const data = await response.json();
    const events: ConstraintEvent[] = [];

    // Handle both array and object formats
    const eventList = Array.isArray(data) ? data : data.events || [];

    for (const evt of eventList) {
      events.push({
        id: evt.id || `event-${events.length}`,
        type: evt.type || 'event',
        timestamp: new Date(evt.time || evt.timestamp),
        message: evt.message || evt.description || '',
        severity: mapSeverity(evt.type || evt.severity),
        value: evt.value,
        limit: evt.limit,
      });
    }

    return events.sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());
  } catch (error) {
    console.warn('Failed to load events:', error);
    return [];
  }
}

async function loadContacts(basePath: string): Promise<ContactWindow[]> {
  try {
    const response = await fetch(`${basePath}/access_windows.json`);
    if (!response.ok) {
      console.warn('Access windows file not found, using empty list');
      return [];
    }

    const data = await response.json();
    const contacts: ContactWindow[] = [];

    // Handle nested station format
    for (const [stationId, windows] of Object.entries(data)) {
      if (Array.isArray(windows)) {
        for (const win of windows as any[]) {
          const aos = new Date(win.aos || win.start);
          const los = new Date(win.los || win.end);

          contacts.push({
            id: `${stationId}-${contacts.length}`,
            stationId,
            stationName: formatStationName(stationId),
            aos,
            los,
            maxElevation: win.max_elevation || win.maxElevation || 0,
            duration: (los.getTime() - aos.getTime()) / 1000,
            scheduledDownlink: win.scheduled_downlink,
            actualDownlink: win.actual_downlink,
          });
        }
      }
    }

    return contacts.sort((a, b) => a.aos.getTime() - b.aos.getTime());
  } catch (error) {
    console.warn('Failed to load contacts:', error);
    return [];
  }
}

async function loadEclipses(basePath: string): Promise<EclipseWindow[]> {
  try {
    const response = await fetch(`${basePath}/eclipse_windows.json`);
    if (!response.ok) {
      return [];
    }

    const data = await response.json();
    const eclipses: EclipseWindow[] = [];

    const windowList = Array.isArray(data) ? data : data.windows || [];

    for (const win of windowList) {
      eclipses.push({
        start: new Date(win.start || win.entry),
        end: new Date(win.end || win.exit),
        type: win.type || 'umbra',
      });
    }

    return eclipses.sort((a, b) => a.start.getTime() - b.start.getTime());
  } catch (error) {
    console.warn('Failed to load eclipses:', error);
    return [];
  }
}

// ============================================
// ALERT CONVERSION
// ============================================

export function eventsToAlerts(events: ConstraintEvent[]): Alert[] {
  return events.map((evt, index) => ({
    id: evt.id || `alert-${index}`,
    type: evt.severity === 'failure' ? 'failure' : evt.severity === 'warning' ? 'warning' : 'event',
    severity: evt.severity,
    timestamp: evt.timestamp,
    title: formatAlertTitle(evt),
    description: evt.message,
    whyItMatters: generateWhyItMatters(evt),
    downstreamImpact: [],
    suggestedActions: generateSuggestedActions(evt),
    rootCauseId: null,
    causedBy: [],
    acknowledged: false,
    expanded: false,
  }));
}

function formatAlertTitle(event: ConstraintEvent): string {
  switch (event.type) {
    case 'soc_violation':
      return 'Battery SOC Violation';
    case 'storage_violation':
      return 'Storage Limit Exceeded';
    case 'propellant_violation':
      return 'Propellant Depleted';
    case 'thermal_violation':
      return 'Temperature Out of Range';
    default:
      return event.type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  }
}

function generateWhyItMatters(event: ConstraintEvent): string {
  switch (event.type) {
    case 'soc_violation':
      return 'Low battery may prevent critical operations and could lead to spacecraft safe mode.';
    case 'storage_violation':
      return 'Insufficient storage prevents new data collection and may delay mission objectives.';
    case 'propellant_violation':
      return 'Propellant depletion limits remaining maneuver capability and mission lifetime.';
    default:
      return 'This constraint violation may impact mission operations.';
  }
}

function generateSuggestedActions(event: ConstraintEvent): Alert['suggestedActions'] {
  switch (event.type) {
    case 'soc_violation':
      return [
        {
          id: 'action-1',
          label: 'Reduce Power Load',
          description: 'Disable non-essential subsystems',
          actionType: 'manual',
        },
        {
          id: 'action-2',
          label: 'Optimize Sun Pointing',
          description: 'Adjust attitude for maximum solar input',
          actionType: 'auto-fix',
        },
      ];
    case 'storage_violation':
      return [
        {
          id: 'action-1',
          label: 'Priority Downlink',
          description: 'Schedule immediate downlink at next contact',
          actionType: 'auto-fix',
        },
      ];
    default:
      return [];
  }
}

// ============================================
// UTILITIES
// ============================================

function mapSeverity(type: string): AlertSeverity {
  if (type.includes('violation') || type.includes('error') || type.includes('failure')) {
    return 'failure';
  }
  if (type.includes('warning')) {
    return 'warning';
  }
  return 'info';
}

function formatStationName(stationId: string): string {
  // Convert station_id to readable name
  return stationId
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

// ============================================
// COMPARISON LOADING
// ============================================

export async function loadCompareData(
  runAPath: string,
  runBPath: string
): Promise<{ runA: RunData; runB: RunData }> {
  const [runA, runB] = await Promise.all([
    loadRunData(runAPath),
    loadRunData(runBPath),
  ]);

  return { runA, runB };
}

export default {
  loadRunData,
  loadCompareData,
  eventsToAlerts,
};
