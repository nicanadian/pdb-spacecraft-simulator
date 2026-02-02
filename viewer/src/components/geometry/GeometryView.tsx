/**
 * Geometry View - 3D CesiumJS Visualization
 * Cinematic Earth with orbital paths and spacecraft
 */

import { Component, onMount, onCleanup, createSignal, Show } from 'solid-js';
import { cesiumService } from '@/services/cesiumService';
import { timeStore } from '@/stores/timeStore';
import { selectionStore } from '@/stores/selectionStore';
import { missionStore } from '@/stores/missionStore';
import { ObjectsPanel } from './ObjectsPanel';
import { TelemetryInspector } from './TelemetryInspector';

interface GeometryViewProps {
  showGhostOrbit?: boolean;
  showDensityLayer?: boolean;
  showSensorFootprint?: boolean;
}

export const GeometryView: Component<GeometryViewProps> = (props) => {
  let containerRef: HTMLDivElement | undefined;
  const [isLoaded, setIsLoaded] = createSignal(false);
  const [objectsPanelOpen, setObjectsPanelOpen] = createSignal(true);
  const [inspectorOpen, setInspectorOpen] = createSignal(true);

  onMount(async () => {
    if (!containerRef) return;

    // Initialize Cesium viewer
    cesiumService.initViewer('cesium-container');

    // Load CZML if run data is available
    const runData = missionStore.state.runData;
    if (runData) {
      try {
        await cesiumService.loadCZML(runData.czmlUrl);

        // Configure clock range
        cesiumService.configureClockRange(
          new Date(runData.manifest.startTime),
          new Date(runData.manifest.endTime),
          timeStore.playbackSpeed()
        );

        setIsLoaded(true);
      } catch (error) {
        console.error('Failed to load CZML:', error);
      }
    }

    // Sync time store with Cesium clock
    const unsubscribeTime = cesiumService.onTimeChange((time) => {
      if (!timeStore.isPlaying()) {
        // Only update from Cesium if we're not controlling playback
      }
    });

    // Sync selection with Cesium entities
    const unsubscribeSelect = cesiumService.onEntitySelect((entityId) => {
      selectionStore.selectEntity(entityId);
    });

    onCleanup(() => {
      unsubscribeTime();
      unsubscribeSelect();
    });
  });

  // Sync playback speed to Cesium
  const syncSpeed = () => {
    cesiumService.setPlaybackMultiplier(timeStore.playbackSpeed());
  };

  // Sync current time to Cesium
  const syncTime = () => {
    cesiumService.setViewerTime(timeStore.currentTime());
  };

  // Watch for time changes
  onMount(() => {
    // Create effect-like behavior for time sync
    const interval = setInterval(() => {
      if (isLoaded()) {
        syncTime();
      }
    }, 100);

    onCleanup(() => clearInterval(interval));
  });

  return (
    <div class="geometry-view">
      {/* Dark frame wrapper */}
      <div class="frame-wrapper">
        {/* Cesium container */}
        <div id="cesium-container" ref={containerRef} class="cesium-container">
          <Show when={!isLoaded()}>
            <div class="loading-overlay">
              <div class="spinner" />
              <p>Loading 3D view...</p>
            </div>
          </Show>
        </div>

        {/* Floating Objects Panel (Left) */}
        <Show when={objectsPanelOpen()}>
          <div class="objects-panel-wrapper glass-floating">
            <ObjectsPanel onClose={() => setObjectsPanelOpen(false)} />
          </div>
        </Show>

        {/* Floating Telemetry Inspector (Right) */}
        <Show when={inspectorOpen() && selectionStore.selectedEntity()}>
          <div class="inspector-wrapper glass-floating">
            <TelemetryInspector onClose={() => setInspectorOpen(false)} />
          </div>
        </Show>

        {/* Viewport Controls (Bottom) */}
        <div class="viewport-controls">
          <button
            class="btn btn-secondary btn-sm"
            classList={{ active: objectsPanelOpen() }}
            onClick={() => setObjectsPanelOpen(!objectsPanelOpen())}
          >
            Objects
          </button>
          <button
            class="btn btn-secondary btn-sm"
            onClick={() => cesiumService.resetView()}
          >
            Reset View
          </button>
          <button
            class="btn btn-secondary btn-sm"
            onClick={() => {
              const entity = selectionStore.selectedEntity();
              if (entity) {
                cesiumService.focusOnEntity(entity);
              }
            }}
            disabled={!selectionStore.selectedEntity()}
          >
            Track
          </button>
        </div>
      </div>

      <style>{`
        .geometry-view {
          width: 100%;
          height: 100%;
          position: relative;
        }

        .frame-wrapper {
          width: 100%;
          height: 100%;
          background: var(--deep-space-navy);
          padding: var(--space-2);
          position: relative;
        }

        .cesium-container {
          width: 100%;
          height: 100%;
          border-radius: var(--radius-lg);
          overflow: hidden;
          position: relative;
        }

        .loading-overlay {
          position: absolute;
          inset: 0;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          background: var(--deep-space-navy);
          color: var(--ghost-slate);
          gap: var(--space-3);
        }

        .loading-overlay p {
          font-size: var(--text-sm);
          color: var(--slate-400);
        }

        /* Floating Panels */
        .objects-panel-wrapper {
          position: absolute;
          top: var(--space-4);
          left: var(--space-4);
          width: 220px;
          max-height: calc(100% - var(--space-8) - 48px);
          overflow: hidden;
        }

        .inspector-wrapper {
          position: absolute;
          top: var(--space-4);
          right: var(--space-4);
          width: 280px;
          max-height: calc(100% - var(--space-8) - 48px);
          overflow: hidden;
        }

        /* Viewport Controls */
        .viewport-controls {
          position: absolute;
          bottom: var(--space-4);
          left: 50%;
          transform: translateX(-50%);
          display: flex;
          gap: var(--space-2);
          padding: var(--space-2);
          background: var(--glass-bg);
          backdrop-filter: var(--glass-blur);
          border-radius: var(--radius-lg);
          border: 1px solid var(--glass-border);
        }

        .viewport-controls .btn.active {
          background: var(--electric-teal);
          color: white;
          border-color: var(--electric-teal);
        }
      `}</style>
    </div>
  );
};
