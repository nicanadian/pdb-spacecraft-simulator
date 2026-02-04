import { For, createMemo } from 'solid-js';
import type { ArchLevel } from '../types/model';
import { activeLevel, setActiveLevel, activeViewpoint, viewpoints } from '../stores/modelStore';

const ALL_LEVELS: ArchLevel[] = ['L0', 'L1', 'L2', 'L3', 'L4'];

export default function LevelSelector() {
  const allowedLevels = createMemo(() => {
    const vp = viewpoints().find(v => v.id === activeViewpoint());
    if (!vp) return new Set(ALL_LEVELS);
    return new Set(vp.include_layers);
  });

  return (
    <div style={{ display: 'flex', gap: '1px', background: '#0f172a', 'border-radius': '6px', padding: '2px' }}>
      <For each={ALL_LEVELS}>
        {(level) => {
          const active = () => activeLevel() === level;
          const enabled = () => allowedLevels().has(level);
          return (
            <button
              onClick={() => enabled() && setActiveLevel(level)}
              disabled={!enabled()}
              style={{
                padding: '3px 8px',
                'border-radius': '4px',
                'font-size': '11px',
                'font-weight': '600',
                background: active() ? '#334155' : 'transparent',
                color: active() ? '#f1f5f9' : enabled() ? '#94a3b8' : '#334155',
                border: 'none',
                cursor: enabled() ? 'pointer' : 'default',
              }}
            >
              {level}
            </button>
          );
        }}
      </For>
    </div>
  );
}
