import { For } from 'solid-js';
import { groups, hiddenGroups, toggleGroup, nodes } from '../stores/modelStore';

export default function FilterPanel() {
  const groupCounts = () => {
    const counts: Record<string, number> = {};
    for (const n of nodes()) {
      counts[n.group] = (counts[n.group] ?? 0) + 1;
    }
    return counts;
  };

  return (
    <div style={{ padding: '0 16px' }}>
      <div style={{ 'font-size': '11px', color: '#94a3b8', 'margin-bottom': '8px', 'text-transform': 'uppercase', 'letter-spacing': '0.05em' }}>
        Groups
      </div>
      <For each={groups()}>
        {(group) => {
          const hidden = () => hiddenGroups().has(group.id);
          const count = () => groupCounts()[group.id] ?? 0;
          return (
            <button
              onClick={() => toggleGroup(group.id)}
              style={{
                display: 'flex',
                'align-items': 'center',
                gap: '8px',
                width: '100%',
                padding: '6px 8px',
                background: 'transparent',
                border: 'none',
                'border-radius': '4px',
                color: hidden() ? '#475569' : '#e2e8f0',
                'font-size': '13px',
                cursor: 'pointer',
                opacity: hidden() ? 0.5 : 1,
                'text-align': 'left',
              }}
            >
              <span style={{
                width: '10px',
                height: '10px',
                'border-radius': '2px',
                background: hidden() ? '#334155' : group.color,
                'flex-shrink': '0',
              }} />
              <span style={{ flex: '1' }}>{group.name}</span>
              <span style={{ 'font-size': '11px', color: '#64748b' }}>{count()}</span>
            </button>
          );
        }}
      </For>
    </div>
  );
}
