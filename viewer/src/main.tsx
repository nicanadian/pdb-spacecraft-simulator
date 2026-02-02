/**
 * Mission Visualization UI - Entry Point
 */

import { render } from 'solid-js/web';

// Log immediately to confirm the script is running
console.log('[main.tsx] Script starting...');

// Import CSS after initial script execution
import('./styles/global.css').then(() => {
  console.log('[main.tsx] Global CSS loaded');
}).catch((err) => {
  console.error('[main.tsx] Failed to load CSS:', err);
});

// Get root element
const root = document.getElementById('root');

if (!root) {
  console.error('[main.tsx] Root element not found!');
} else {
  console.log('[main.tsx] Root element found, importing App...');

  // Clear the initial loader
  root.innerHTML = '';

  // Dynamically import App to catch any errors
  import('./App').then(({ default: App }) => {
    console.log('[main.tsx] App imported, rendering...');
    try {
      render(() => <App />, root);
      console.log('[main.tsx] App rendered successfully');
    } catch (err) {
      console.error('[main.tsx] Failed to render App:', err);
      root.innerHTML = `
        <div style="padding: 40px; color: #DC2626; font-family: monospace; background: #0F172A; height: 100%;">
          <h2>Render Error</h2>
          <pre>${err instanceof Error ? err.stack : String(err)}</pre>
        </div>
      `;
    }
  }).catch((err) => {
    console.error('[main.tsx] Failed to import App:', err);
    root.innerHTML = `
      <div style="padding: 40px; color: #DC2626; font-family: monospace; background: #0F172A; height: 100%;">
        <h2>Import Error</h2>
        <pre>${err instanceof Error ? err.stack : String(err)}</pre>
      </div>
    `;
  });
}
