/**
 * Mission Store - Core State Management
 * Implements the Operational Triad invariant:
 * Sequence (Intent) <-> Timeline (Time) <-> Geometry (Space)
 */

import { createSignal, createEffect, batch } from 'solid-js';
import { createStore, produce } from 'solid-js/store';
import type {
  Activity,
  Alert,
  RunData,
  WorkspaceId,
  BranchState,
  Branch,
  UndoAction,
  CommandMode,
  TimeRange,
  SpacecraftState,
} from '@/types';

// ============================================
// CORE MISSION STATE
// ============================================

export interface MissionState {
  // Run Data
  runData: RunData | null;
  baselineData: RunData | null;
  branchData: RunData | null;

  // Loading
  isLoading: boolean;
  loadError: string | null;

  // Workspace
  activeWorkspace: WorkspaceId;

  // Branching
  branchState: BranchState;
  activeBranch: Branch | null;

  // Alerts
  alerts: Alert[];
  unacknowledgedCount: number;

  // Undo/Redo
  undoStack: UndoAction[];
  redoStack: UndoAction[];

  // Command Mode
  commandMode: CommandMode;
}

const initialState: MissionState = {
  runData: null,
  baselineData: null,
  branchData: null,
  isLoading: false,
  loadError: null,
  activeWorkspace: 'mission-overview',
  branchState: 'none',
  activeBranch: null,
  alerts: [],
  unacknowledgedCount: 0,
  undoStack: [],
  redoStack: [],
  commandMode: 'read-only',
};

const [state, setState] = createStore<MissionState>(initialState);

// ============================================
// RUN DATA ACTIONS
// ============================================

export function setRunData(data: RunData): void {
  setState(
    produce((s) => {
      s.runData = data;
      s.isLoading = false;
      s.loadError = null;
    })
  );
}

export function setBaselineData(data: RunData | null): void {
  setState('baselineData', data);
}

export function setLoading(loading: boolean): void {
  setState('isLoading', loading);
}

export function setLoadError(error: string | null): void {
  setState(
    produce((s) => {
      s.loadError = error;
      s.isLoading = false;
    })
  );
}

// ============================================
// WORKSPACE ACTIONS
// ============================================

export function setActiveWorkspace(workspace: WorkspaceId): void {
  setState('activeWorkspace', workspace);
}

// ============================================
// BRANCHING ACTIONS
// ============================================

export function enterBranchMode(): void {
  if (state.branchState === 'none' && state.runData) {
    const branch: Branch = {
      id: `branch-${Date.now()}`,
      name: 'What-If Analysis',
      createdAt: new Date(),
      baselineRunId: state.runData.manifest.planId,
      modifications: [],
    };

    setState(
      produce((s) => {
        s.branchState = 'active';
        s.activeBranch = branch;
        s.baselineData = s.runData;
      })
    );
  }
}

export function exitBranchMode(commit: boolean): void {
  if (commit && state.activeBranch) {
    // Apply branch changes to main data
    // TODO: Implement branch commit logic
  }

  setState(
    produce((s) => {
      s.branchState = 'none';
      s.activeBranch = null;
      if (!commit) {
        s.baselineData = null;
      }
    })
  );
}

export function enterCompareMode(): void {
  if (state.baselineData) {
    setState('branchState', 'comparing');
  }
}

// ============================================
// ALERT ACTIONS
// ============================================

export function setAlerts(alerts: Alert[]): void {
  setState(
    produce((s) => {
      s.alerts = alerts;
      s.unacknowledgedCount = alerts.filter((a) => !a.acknowledged).length;
    })
  );
}

export function acknowledgeAlert(alertId: string): void {
  setState(
    produce((s) => {
      const alert = s.alerts.find((a) => a.id === alertId);
      if (alert) {
        alert.acknowledged = true;
        s.unacknowledgedCount = s.alerts.filter((a) => !a.acknowledged).length;
      }
    })
  );
}

export function toggleAlertExpanded(alertId: string): void {
  setState(
    produce((s) => {
      const alert = s.alerts.find((a) => a.id === alertId);
      if (alert) {
        alert.expanded = !alert.expanded;
      }
    })
  );
}

// ============================================
// UNDO/REDO ACTIONS
// ============================================

export function pushUndoAction(action: UndoAction): void {
  setState(
    produce((s) => {
      s.undoStack.push(action);
      s.redoStack = []; // Clear redo on new action
    })
  );
}

export function undo(): UndoAction | null {
  const action = state.undoStack[state.undoStack.length - 1];
  if (!action) return null;

  setState(
    produce((s) => {
      const popped = s.undoStack.pop();
      if (popped) {
        s.redoStack.push(popped);
      }
    })
  );

  return action;
}

export function redo(): UndoAction | null {
  const action = state.redoStack[state.redoStack.length - 1];
  if (!action) return null;

  setState(
    produce((s) => {
      const popped = s.redoStack.pop();
      if (popped) {
        s.undoStack.push(popped);
      }
    })
  );

  return action;
}

// ============================================
// COMMAND MODE ACTIONS
// ============================================

export function setCommandMode(mode: CommandMode): void {
  setState('commandMode', mode);
}

// ============================================
// SELECTORS (derived state)
// ============================================

export function getState(): MissionState {
  return state;
}

export function isInBranchMode(): boolean {
  return state.branchState === 'active';
}

export function isComparing(): boolean {
  return state.branchState === 'comparing';
}

export function hasUnsavedChanges(): boolean {
  return state.undoStack.length > 0;
}

export function canUndo(): boolean {
  return state.undoStack.length > 0;
}

export function canRedo(): boolean {
  return state.redoStack.length > 0;
}

// ============================================
// STORE EXPORT
// ============================================

export const missionStore = {
  state,
  setState,
  // Actions
  setRunData,
  setBaselineData,
  setLoading,
  setLoadError,
  setActiveWorkspace,
  enterBranchMode,
  exitBranchMode,
  enterCompareMode,
  setAlerts,
  acknowledgeAlert,
  toggleAlertExpanded,
  pushUndoAction,
  undo,
  redo,
  setCommandMode,
  // Selectors
  getState,
  isInBranchMode,
  isComparing,
  hasUnsavedChanges,
  canUndo,
  canRedo,
};

export default missionStore;
