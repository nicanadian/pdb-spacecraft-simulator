import { For } from 'solid-js';
import type { ViewId } from '../types/model';
import { activeViewpoint, setActiveViewpoint, hasArchModel } from '../stores/modelStore';

const VIEWPOINTS: { id: ViewId; label: string }[] = [
  { id: 'operational-context', label: 'Context' },
  { id: 'capability-map', label: 'Capabilities' },
  { id: 'logical-architecture', label: 'Logical' },
  { id: 'interface-contracts', label: 'Interfaces' },
  { id: 'technical-deployment', label: 'Technical' },
  { id: 'requirements-decomposition', label: 'Requirements' },
];

export default function ViewpointSelector() {
  return (
    <div style={{ display: 'flex', gap: '2px', background: '#0f172a', 'border-radius': '8px', padding: '2px' }}>
      <For each={VIEWPOINTS}>
        {(vp) => {
          const active = () => activeViewpoint() === vp.id;
          return (
            <button
              onClick={() => setActiveViewpoint(vp.id)}
              disabled={!hasArchModel()}
              style={{
                padding: '5px 10px',
                'border-radius': '6px',
                'font-size': '12px',
                background: active() ? '#334155' : 'transparent',
                color: active() ? '#f1f5f9' : '#94a3b8',
                border: 'none',
                cursor: hasArchModel() ? 'pointer' : 'default',
                'font-weight': active() ? '500' : '400',
                opacity: hasArchModel() ? 1 : 0.4,
                'white-space': 'nowrap',
              }}
            >
              {vp.label}
            </button>
          );
        }}
      </For>
    </div>
  );
}
