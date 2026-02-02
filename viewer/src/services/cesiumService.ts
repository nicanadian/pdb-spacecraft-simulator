/**
 * Cesium Service
 * Handles all CesiumJS integration and viewer management
 *
 * NOTE: This service is configured for OFFLINE use only.
 * No Cesium Ion account or token is required.
 * All assets are served locally via vite-plugin-cesium.
 */

import * as Cesium from 'cesium';
import 'cesium/Build/Cesium/Widgets/widgets.css';
import type { CameraPosition, TimeRange } from '@/types';

// ============================================
// DISABLE CESIUM ION COMPLETELY
// Must be done before any Cesium objects are created
// ============================================
Cesium.Ion.defaultAccessToken = '';

// ============================================
// TYPES
// ============================================

export interface CesiumViewerInstance {
  viewer: Cesium.Viewer;
  dataSource: Cesium.CzmlDataSource | null;
}

let viewerInstance: CesiumViewerInstance | null = null;

// ============================================
// VIEWER INITIALIZATION
// ============================================

export function initViewer(containerId: string): CesiumViewerInstance {
  // Create imagery provider using built-in Natural Earth II (no Ion required)
  const imageryProvider = new Cesium.TileMapServiceImageryProvider({
    url: Cesium.buildModuleUrl('Assets/Textures/NaturalEarthII'),
  });

  const viewer = new Cesium.Viewer(containerId, {
    // Disable default UI elements we don't need
    baseLayerPicker: false,
    geocoder: false,
    timeline: false,
    animation: false,
    vrButton: false,
    navigationHelpButton: false,
    sceneModePicker: true,
    homeButton: true,
    fullscreenButton: true,
    infoBox: true,
    selectionIndicator: true,

    // Use local imagery - no Ion required
    imageryProvider: imageryProvider,

    // Use ellipsoid terrain (flat) - no Ion required
    terrainProvider: new Cesium.EllipsoidTerrainProvider(),

    // Scene settings
    skyBox: false,
    skyAtmosphere: false,
    requestRenderMode: false,
    maximumRenderTimeChange: Infinity,
  });

  // Configure scene for cinematic look
  configureScene(viewer);

  // Set initial camera position
  setInitialCamera(viewer);

  // Configure clock for manual control
  viewer.clock.shouldAnimate = false;
  viewer.clock.clockStep = Cesium.ClockStep.SYSTEM_CLOCK_MULTIPLIER;
  viewer.clock.multiplier = 60;

  viewerInstance = {
    viewer,
    dataSource: null,
  };

  // Expose for debugging
  (window as any).cesiumViewer = viewer;

  return viewerInstance;
}

function configureScene(viewer: Cesium.Viewer): void {
  const scene = viewer.scene;

  // Cinematic background (deep space navy)
  scene.backgroundColor = Cesium.Color.fromCssColorString('#0F172A');

  // Globe settings
  scene.globe.baseColor = Cesium.Color.fromCssColorString('#1E293B');
  scene.globe.enableLighting = false;
  scene.globe.showGroundAtmosphere = false;

  // Atmosphere for glow effect
  scene.skyAtmosphere = new Cesium.SkyAtmosphere();
  scene.skyAtmosphere.brightnessShift = 0.1;
  scene.skyAtmosphere.saturationShift = -0.2;
  scene.skyAtmosphere.hueShift = 0.0;

  // Disable HDR for consistent colors
  scene.highDynamicRange = false;

  // Enable anti-aliasing
  scene.postProcessStages.fxaa.enabled = true;

  // Shadows off for performance
  viewer.shadows = false;
}

function setInitialCamera(viewer: Cesium.Viewer): void {
  // Initial view: Looking at Earth from ~20,000 km
  viewer.camera.setView({
    destination: Cesium.Cartesian3.fromDegrees(0, 20, 20000000),
    orientation: {
      heading: 0,
      pitch: Cesium.Math.toRadians(-90),
      roll: 0,
    },
  });
}

// ============================================
// CZML LOADING
// ============================================

export async function loadCZML(czmlUrl: string): Promise<Cesium.CzmlDataSource> {
  if (!viewerInstance) {
    throw new Error('Viewer not initialized');
  }

  const { viewer } = viewerInstance;

  // Remove existing data source if present
  if (viewerInstance.dataSource) {
    viewer.dataSources.remove(viewerInstance.dataSource);
  }

  // Load new CZML
  const dataSource = await Cesium.CzmlDataSource.load(czmlUrl);

  // Add to viewer
  await viewer.dataSources.add(dataSource);

  viewerInstance.dataSource = dataSource;

  return dataSource;
}

// ============================================
// TIME CONTROL
// ============================================

export function setViewerTime(time: Date): void {
  if (!viewerInstance) return;

  const julianDate = Cesium.JulianDate.fromDate(time);
  viewerInstance.viewer.clock.currentTime = julianDate;
}

export function configureClockRange(
  startTime: Date,
  endTime: Date,
  multiplier: number = 60
): void {
  if (!viewerInstance) return;

  const clock = viewerInstance.viewer.clock;
  clock.startTime = Cesium.JulianDate.fromDate(startTime);
  clock.stopTime = Cesium.JulianDate.fromDate(endTime);
  clock.currentTime = Cesium.JulianDate.fromDate(startTime);
  clock.multiplier = multiplier;
  clock.clockRange = Cesium.ClockRange.CLAMPED;
}

export function setPlaybackMultiplier(multiplier: number): void {
  if (!viewerInstance) return;
  viewerInstance.viewer.clock.multiplier = multiplier;
}

export function startClock(): void {
  if (!viewerInstance) return;
  viewerInstance.viewer.clock.shouldAnimate = true;
}

export function stopClock(): void {
  if (!viewerInstance) return;
  viewerInstance.viewer.clock.shouldAnimate = false;
}

// ============================================
// ENTITY MANAGEMENT
// ============================================

export function focusOnEntity(entityId: string): void {
  if (!viewerInstance?.dataSource) return;

  const entity = viewerInstance.dataSource.entities.getById(entityId);
  if (entity) {
    viewerInstance.viewer.trackedEntity = entity;
  }
}

export function clearTracking(): void {
  if (!viewerInstance) return;
  viewerInstance.viewer.trackedEntity = undefined;
}

export function getEntityById(entityId: string): Cesium.Entity | undefined {
  return viewerInstance?.dataSource?.entities.getById(entityId);
}

export function getAllEntities(): Cesium.Entity[] {
  if (!viewerInstance?.dataSource) return [];
  return viewerInstance.dataSource.entities.values;
}

// ============================================
// CAMERA CONTROL
// ============================================

export function flyTo(position: CameraPosition, duration: number = 2): void {
  if (!viewerInstance) return;

  viewerInstance.viewer.camera.flyTo({
    destination: Cesium.Cartesian3.fromDegrees(
      position.longitude,
      position.latitude,
      position.height
    ),
    orientation: {
      heading: Cesium.Math.toRadians(position.heading || 0),
      pitch: Cesium.Math.toRadians(position.pitch || -90),
      roll: Cesium.Math.toRadians(position.roll || 0),
    },
    duration,
    easingFunction: Cesium.EasingFunction.QUINTIC_IN_OUT,
  });
}

export function zoomToEntity(entityId: string): void {
  if (!viewerInstance?.dataSource) return;

  const entity = viewerInstance.dataSource.entities.getById(entityId);
  if (entity) {
    viewerInstance.viewer.zoomTo(entity, {
      heading: 0,
      pitch: Cesium.Math.toRadians(-45),
      range: 5000000,
    });
  }
}

export function resetView(): void {
  if (!viewerInstance) return;
  setInitialCamera(viewerInstance.viewer);
}

// ============================================
// VISUALIZATION PRIMITIVES
// ============================================

export function addOrbitPath(
  positions: Cesium.Cartesian3[],
  options: {
    color?: string;
    width?: number;
    dashed?: boolean;
    ghost?: boolean;
  } = {}
): Cesium.Primitive {
  if (!viewerInstance) throw new Error('Viewer not initialized');

  const color = options.ghost
    ? Cesium.Color.fromCssColorString('#0F172A').withAlpha(0.4)
    : Cesium.Color.fromCssColorString(options.color || '#0891B2');

  const material = options.dashed
    ? new Cesium.PolylineDashMaterialProperty({
        color: color,
        dashLength: 16,
        dashPattern: 255,
      })
    : new Cesium.ColorMaterialProperty(color);

  const polyline = viewerInstance.viewer.entities.add({
    polyline: {
      positions: positions,
      width: options.width || 2,
      material: material as any,
      clampToGround: false,
    },
  });

  return polyline as unknown as Cesium.Primitive;
}

export function addGroundStation(
  longitude: number,
  latitude: number,
  name: string,
  options: { color?: string } = {}
): Cesium.Entity {
  if (!viewerInstance) throw new Error('Viewer not initialized');

  const color = Cesium.Color.fromCssColorString(options.color || '#0891B2');

  return viewerInstance.viewer.entities.add({
    name: name,
    position: Cesium.Cartesian3.fromDegrees(longitude, latitude, 0),
    point: {
      pixelSize: 8,
      color: color,
      outlineColor: Cesium.Color.WHITE,
      outlineWidth: 1,
    },
    label: {
      text: name,
      font: '12px Inter, sans-serif',
      fillColor: Cesium.Color.WHITE,
      outlineColor: Cesium.Color.BLACK,
      outlineWidth: 1,
      style: Cesium.LabelStyle.FILL_AND_OUTLINE,
      verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
      pixelOffset: new Cesium.Cartesian2(0, -12),
    },
  });
}

// ============================================
// EVENT HANDLING
// ============================================

export function onEntitySelect(
  callback: (entityId: string | null) => void
): () => void {
  if (!viewerInstance) return () => {};

  const handler = new Cesium.ScreenSpaceEventHandler(
    viewerInstance.viewer.scene.canvas
  );

  handler.setInputAction((click: { position: Cesium.Cartesian2 }) => {
    const picked = viewerInstance!.viewer.scene.pick(click.position);
    if (Cesium.defined(picked) && picked.id) {
      callback(picked.id.id || picked.id.name || null);
    } else {
      callback(null);
    }
  }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

  return () => handler.destroy();
}

export function onTimeChange(callback: (time: Date) => void): () => void {
  if (!viewerInstance) return () => {};

  const listener = viewerInstance.viewer.clock.onTick.addEventListener(() => {
    const julianDate = viewerInstance!.viewer.clock.currentTime;
    callback(Cesium.JulianDate.toDate(julianDate));
  });

  return () => listener();
}

// ============================================
// CLEANUP
// ============================================

export function destroyViewer(): void {
  if (viewerInstance) {
    viewerInstance.viewer.destroy();
    viewerInstance = null;
  }
}

export function getViewer(): Cesium.Viewer | null {
  return viewerInstance?.viewer || null;
}

// ============================================
// EXPORT
// ============================================

export const cesiumService = {
  initViewer,
  loadCZML,
  setViewerTime,
  configureClockRange,
  setPlaybackMultiplier,
  startClock,
  stopClock,
  focusOnEntity,
  clearTracking,
  getEntityById,
  getAllEntities,
  flyTo,
  zoomToEntity,
  resetView,
  addOrbitPath,
  addGroundStation,
  onEntitySelect,
  onTimeChange,
  destroyViewer,
  getViewer,
};

export default cesiumService;
