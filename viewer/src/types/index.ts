/**
 * Mission Visualization UI - Core Types
 */

// ============================================
// TIME & TEMPORAL
// ============================================

export interface TimeRange {
  start: Date;
  end: Date;
}

export type PlaybackSpeed = 1 | 10 | 60 | 300 | 1000;

// ============================================
// ACTIVITIES & SEQUENCE
// ============================================

export type ActivityType =
  | 'propagate'
  | 'maneuver'
  | 'attitude_slew'
  | 'imaging'
  | 'downlink'
  | 'idle'
  | 'eclipse'
  | 'maintenance';

export interface Activity {
  id: string;
  type: ActivityType;
  name: string;
  startTime: Date;
  endTime: Date;
  duration: number; // seconds
  parameters: Record<string, unknown>;
  parentId?: string;
  children?: Activity[];
  status: 'pending' | 'active' | 'completed';
}

export interface ManeuverParameters {
  deltaV: number; // m/s
  burnDuration: number; // seconds
  thrustDirection: [number, number, number];
}

// ============================================
// ALERTS & EVENTS
// ============================================

export type AlertSeverity = 'info' | 'warning' | 'failure';

export interface Alert {
  id: string;
  type: 'event' | 'warning' | 'failure';
  severity: AlertSeverity;
  timestamp: Date;
  title: string;
  description: string;

  // Per spec 7.3 - required context
  whyItMatters: string;
  downstreamImpact: Alert[];
  suggestedActions: SuggestedAction[];

  // Causal linking
  rootCauseId: string | null;
  causedBy: string[];

  // Activity association
  activityId?: string;

  // UI state
  acknowledged: boolean;
  expanded: boolean;
}

export interface SuggestedAction {
  id: string;
  label: string;
  description: string;
  actionType: 'auto-fix' | 'manual' | 'navigate';
  parameters?: Record<string, unknown>;
}

export interface ConstraintEvent {
  id: string;
  type: string;
  timestamp: Date;
  message: string;
  severity: AlertSeverity;
  value?: number;
  limit?: number;
}

// ============================================
// GROUND CONTACTS
// ============================================

export interface GroundStation {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  altitude: number;
  minElevation: number;
}

export interface ContactWindow {
  id: string;
  stationId: string;
  stationName: string;
  aos: Date; // Acquisition of Signal
  los: Date; // Loss of Signal
  maxElevation: number;
  duration: number; // seconds
  scheduledDownlink?: number; // bytes
  actualDownlink?: number; // bytes
}

// ============================================
// SPACECRAFT STATE
// ============================================

export interface SpacecraftState {
  timestamp: Date;
  position: [number, number, number]; // ECI km
  velocity: [number, number, number]; // ECI km/s
  altitude: number; // km
  latitude: number;
  longitude: number;
  attitude?: [number, number, number, number]; // quaternion

  // Resources
  soc: number; // State of charge [0, 1]
  storageUsed: number; // bytes
  storageCapacity: number; // bytes
  propellantMass: number; // kg

  // Thermal
  temperature?: number; // Kelvin

  // Eclipse
  inEclipse: boolean;
}

export interface OrbitalElements {
  semiMajorAxis: number;
  eccentricity: number;
  inclination: number;
  raan: number;
  argumentOfPerigee: number;
  trueAnomaly: number;
  period: number;
  apogee: number;
  perigee: number;
}

// ============================================
// RUN DATA
// ============================================

export interface RunManifest {
  planId: string;
  fidelity: 'LOW' | 'MEDIUM' | 'HIGH';
  durationHours: number;
  startTime: string;
  endTime: string;
  spacecraftId: string;
  tle?: string[];
}

export interface RunData {
  manifest: RunManifest;
  events: ConstraintEvent[];
  contacts: ContactWindow[];
  eclipses: EclipseWindow[];
  czmlUrl: string;
}

export interface EclipseWindow {
  start: Date;
  end: Date;
  type: 'umbra' | 'penumbra';
}

// ============================================
// WORKSPACES
// ============================================

export type WorkspaceId =
  | 'mission-overview'
  | 'maneuver-planning'
  | 'vleo-drag'
  | 'anomaly-response'
  | 'payload-ops';

export interface WorkspaceConfig {
  id: WorkspaceId;
  name: string;
  description: string;
  icon: string;
  layout: PanelLayout;
  defaultFilters?: Record<string, unknown>;
}

export interface PanelLayout {
  sequence: PanelConfig;
  timeline: PanelConfig;
  geometry: PanelConfig;
  inspector: PanelConfig;
  alerts?: PanelConfig;
}

export interface PanelConfig {
  visible: boolean;
  width?: number;
  height?: number;
  position?: 'left' | 'right' | 'bottom' | 'center';
  collapsed?: boolean;
}

// ============================================
// COMPARISON & BRANCHING
// ============================================

export type BranchState = 'none' | 'active' | 'comparing';

export interface Branch {
  id: string;
  name: string;
  createdAt: Date;
  baselineRunId: string;
  modifications: Modification[];
  computedResults?: RunData;
}

export interface Modification {
  id: string;
  type: 'parameter_change' | 'activity_add' | 'activity_remove' | 'activity_move';
  targetId: string;
  field?: string;
  oldValue?: unknown;
  newValue?: unknown;
  timestamp: Date;
}

export interface ComparisonMetrics {
  positionRmse: number;
  contactDeltaSeconds: number;
  socDelta: number;
  storageDelta: number;
  warnings: string[];
}

// ============================================
// UNDO/REDO
// ============================================

export interface UndoAction {
  id: string;
  description: string;
  semanticExplanation: string;
  timestamp: Date;
  modifications: Modification[];
  impacts: Impact[];
}

export interface Impact {
  metric: string;
  delta: number;
  severity: 'positive' | 'neutral' | 'negative';
}

// ============================================
// CESIUM INTEGRATION
// ============================================

export interface CesiumViewerRef {
  viewer: unknown; // Cesium.Viewer
  dataSource: unknown; // Cesium.CzmlDataSource
}

export interface CameraPosition {
  longitude: number;
  latitude: number;
  height: number;
  heading?: number;
  pitch?: number;
  roll?: number;
}

// ============================================
// UI STATE
// ============================================

export type CommandMode = 'read-only' | 'command-capable';

export interface ToastNotification {
  id: string;
  type: 'info' | 'success' | 'warning' | 'error';
  title: string;
  message: string;
  duration?: number;
  action?: {
    label: string;
    onClick: () => void;
  };
}
