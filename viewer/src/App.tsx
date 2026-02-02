/**
 * Mission Visualization UI - Root Application Component
 */

import { Component, createSignal, onMount, Show } from 'solid-js';

// Simple test first - delay loading the complex components
const App: Component = () => {
  const [ready, setReady] = createSignal(false);
  const [error, setError] = createSignal<string | null>(null);

  onMount(async () => {
    console.log('[App] Component mounted');

    try {
      // Dynamically import the stores and services
      console.log('[App] Importing stores...');
      const { missionStore } = await import('./stores/missionStore');
      const { timeStore } = await import('./stores/timeStore');
      const { loadRunData, eventsToAlerts } = await import('./services/dataLoader');

      console.log('[App] Loading run data...');
      const runPath = new URLSearchParams(window.location.search).get('run') || '/sample_run';

      const runData = await loadRunData(runPath);
      console.log('[App] Run data loaded:', runData.manifest);

      missionStore.setRunData(runData);
      const alerts = eventsToAlerts(runData.events);
      missionStore.setAlerts(alerts);

      if (runData.manifest.startTime && runData.manifest.endTime) {
        timeStore.initializeTimeRange(runData.manifest.startTime, runData.manifest.endTime);
      }

      setReady(true);
    } catch (err) {
      console.error('[App] Error:', err);
      setError(err instanceof Error ? err.message : String(err));
    }
  });

  return (
    <div style={{ width: '100%', height: '100%' }}>
      <Show when={error()}>
        <div style={{
          padding: '40px',
          'text-align': 'center',
          background: '#0F172A',
          color: '#F8FAFC',
          height: '100%',
          display: 'flex',
          'flex-direction': 'column',
          'align-items': 'center',
          'justify-content': 'center',
        }}>
          <h2 style={{ color: '#DC2626', 'margin-bottom': '16px' }}>Error Loading</h2>
          <p style={{ 'font-family': 'monospace', 'max-width': '600px', 'word-break': 'break-all' }}>
            {error()}
          </p>
          <button
            onClick={() => window.location.reload()}
            style={{
              'margin-top': '20px',
              padding: '10px 20px',
              background: '#0891B2',
              color: 'white',
              border: 'none',
              'border-radius': '6px',
              cursor: 'pointer'
            }}
          >
            Retry
          </button>
        </div>
      </Show>

      <Show when={!error() && !ready()}>
        <div style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          'flex-direction': 'column',
          'align-items': 'center',
          'justify-content': 'center',
          background: '#0F172A',
          color: '#F8FAFC',
        }}>
          <div style={{
            width: '24px',
            height: '24px',
            border: '2px solid #334155',
            'border-top-color': '#0891B2',
            'border-radius': '50%',
            animation: 'spin 0.6s linear infinite',
          }} />
          <p style={{ 'margin-top': '16px', color: '#94A3B8' }}>Loading mission data...</p>
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
      </Show>

      <Show when={ready() && !error()}>
        <AppContent />
      </Show>
    </div>
  );
};

// Separate component for the actual app content
const AppContent: Component = () => {
  // Dynamically import AppShell when ready
  const [Shell, setShell] = createSignal<Component | null>(null);

  onMount(async () => {
    try {
      console.log('[AppContent] Loading AppShell...');
      const { AppShell } = await import('./components/shell/AppShell');
      setShell(() => AppShell);
      console.log('[AppContent] AppShell loaded');
    } catch (err) {
      console.error('[AppContent] Failed to load AppShell:', err);
    }
  });

  return (
    <Show
      when={Shell()}
      fallback={
        <div style={{ padding: '40px', color: '#94A3B8', 'text-align': 'center' }}>
          Loading UI components...
        </div>
      }
    >
      {(ShellComponent) => <ShellComponent />}
    </Show>
  );
};

export default App;
