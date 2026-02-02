/**
 * Selection Store - Triad Link State Management
 *
 * Implements the Operational Triad invariant:
 * "Any interaction in one domain MUST resolve into the other two"
 *
 * Selection in:
 * - Sequence Panel -> Updates timeline position + geometry focus
 * - Timeline -> Updates sequence highlight + geometry view
 * - Geometry -> Updates sequence highlight + timeline position
 */

import { createSignal, createEffect, batch } from 'solid-js';
import type { Activity, ContactWindow, Alert, TimeRange } from '@/types';
import { timeStore } from './timeStore';

// ============================================
// SELECTION STATE
// ============================================

// Primary selections
const [selectedActivity, setSelectedActivityInternal] = createSignal<Activity | null>(null);
const [selectedContact, setSelectedContactInternal] = createSignal<ContactWindow | null>(null);
const [selectedAlert, setSelectedAlertInternal] = createSignal<Alert | null>(null);
const [selectedEntity, setSelectedEntityInternal] = createSignal<string | null>(null);

// Time-based selection
const [selectedTimeRange, setSelectedTimeRange] = createSignal<TimeRange | null>(null);

// Hover states (for preview highlighting)
const [hoveredActivity, setHoveredActivity] = createSignal<Activity | null>(null);
const [hoveredEntity, setHoveredEntity] = createSignal<string | null>(null);
const [hoveredTime, setHoveredTime] = createSignal<Date | null>(null);

// Multi-selection (for batch operations)
const [multiSelectedActivities, setMultiSelectedActivities] = createSignal<Activity[]>([]);

// ============================================
// TRIAD-LINKED SELECTION ACTIONS
// ============================================

/**
 * Select an activity - enforces Triad invariant
 * Updates: timeline position, geometry focus
 */
function selectActivity(activity: Activity | null, options?: { skipTimeJump?: boolean }): void {
  batch(() => {
    setSelectedActivityInternal(activity);
    setSelectedContact(null);
    setSelectedAlert(null);

    if (activity) {
      // Update entity selection for geometry view
      setSelectedEntityInternal(activity.id);

      // Jump timeline to activity start (unless opted out)
      if (!options?.skipTimeJump) {
        timeStore.jumpToTime(activity.startTime);
      }

      // Set time range selection to activity duration
      setSelectedTimeRange({
        start: activity.startTime,
        end: activity.endTime,
      });
    } else {
      setSelectedEntityInternal(null);
      setSelectedTimeRange(null);
    }
  });
}

/**
 * Select a contact window - enforces Triad invariant
 */
function selectContact(contact: ContactWindow | null): void {
  batch(() => {
    setSelectedContactInternal(contact);
    setSelectedActivity(null);
    setSelectedAlert(null);

    if (contact) {
      setSelectedEntityInternal(contact.stationId);
      timeStore.jumpToTime(contact.aos);
      setSelectedTimeRange({
        start: contact.aos,
        end: contact.los,
      });
    } else {
      setSelectedEntityInternal(null);
      setSelectedTimeRange(null);
    }
  });
}

/**
 * Select an alert - enforces Triad invariant
 */
function selectAlert(alert: Alert | null): void {
  batch(() => {
    setSelectedAlertInternal(alert);
    setSelectedContact(null);

    if (alert) {
      timeStore.jumpToTime(alert.timestamp);

      // If alert is associated with an activity, select it
      if (alert.activityId) {
        // Note: Activity lookup would happen in the component using this
        setSelectedEntityInternal(alert.activityId);
      }
    } else {
      if (!selectedActivity()) {
        setSelectedEntityInternal(null);
      }
    }
  });
}

/**
 * Select an entity from the geometry view - enforces Triad invariant
 */
function selectEntity(entityId: string | null): void {
  batch(() => {
    setSelectedEntityInternal(entityId);

    // Clear other selections if selecting nothing
    if (!entityId) {
      setSelectedActivityInternal(null);
      setSelectedContactInternal(null);
      setSelectedAlertInternal(null);
      setSelectedTimeRange(null);
    }
    // Note: Mapping entity to activity would happen in the component
  });
}

/**
 * Select a time range from the timeline
 */
function selectTimeRange(range: TimeRange | null): void {
  setSelectedTimeRange(range);
  if (range) {
    // Jump to start of selected range
    timeStore.jumpToTime(range.start);
  }
}

// ============================================
// MULTI-SELECTION
// ============================================

function toggleMultiSelectActivity(activity: Activity): void {
  setMultiSelectedActivities((prev) => {
    const index = prev.findIndex((a) => a.id === activity.id);
    if (index >= 0) {
      return [...prev.slice(0, index), ...prev.slice(index + 1)];
    } else {
      return [...prev, activity];
    }
  });
}

function clearMultiSelection(): void {
  setMultiSelectedActivities([]);
}

function isMultiSelected(activityId: string): boolean {
  return multiSelectedActivities().some((a) => a.id === activityId);
}

// ============================================
// CLEAR SELECTIONS
// ============================================

function clearAllSelections(): void {
  batch(() => {
    setSelectedActivityInternal(null);
    setSelectedContactInternal(null);
    setSelectedAlertInternal(null);
    setSelectedEntityInternal(null);
    setSelectedTimeRange(null);
    setMultiSelectedActivities([]);
  });
}

function clearHoverStates(): void {
  batch(() => {
    setHoveredActivity(null);
    setHoveredEntity(null);
    setHoveredTime(null);
  });
}

// ============================================
// SELECTION QUERIES
// ============================================

function hasSelection(): boolean {
  return !!(
    selectedActivity() ||
    selectedContact() ||
    selectedAlert() ||
    selectedEntity()
  );
}

function getSelectionType(): 'activity' | 'contact' | 'alert' | 'entity' | null {
  if (selectedActivity()) return 'activity';
  if (selectedContact()) return 'contact';
  if (selectedAlert()) return 'alert';
  if (selectedEntity()) return 'entity';
  return null;
}

// ============================================
// STORE EXPORT
// ============================================

export const selectionStore = {
  // Signals
  selectedActivity,
  selectedContact,
  selectedAlert,
  selectedEntity,
  selectedTimeRange,
  hoveredActivity,
  hoveredEntity,
  hoveredTime,
  multiSelectedActivities,

  // Triad-linked actions
  selectActivity,
  selectContact,
  selectAlert,
  selectEntity,
  selectTimeRange,

  // Hover actions
  setHoveredActivity,
  setHoveredEntity,
  setHoveredTime,

  // Multi-selection
  toggleMultiSelectActivity,
  clearMultiSelection,
  isMultiSelected,

  // Clear
  clearAllSelections,
  clearHoverStates,

  // Queries
  hasSelection,
  getSelectionType,
};

// Also export individual setters for direct use
export {
  setSelectedActivityInternal as setSelectedActivity,
  setSelectedContactInternal as setSelectedContact,
};

export default selectionStore;
