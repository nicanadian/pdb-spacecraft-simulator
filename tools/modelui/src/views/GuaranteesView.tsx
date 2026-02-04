import { For, createSignal, createMemo } from 'solid-js';
import { invariants, setActiveView, setSelectedNodeId, nodes } from '../stores/modelStore';

type SortField = 'severity' | 'source' | 'id';
const SEVERITY_ORDER: Record<string, number> = { must: 0, should: 1, info: 2 };

export default function GuaranteesView() {
  const [sortField, setSortField] = createSignal<SortField>('severity');

  const sorted = createMemo(() => {
    const field = sortField();
    return [...invariants()].sort((a, b) => {
      if (field === 'severity') {
        return (SEVERITY_ORDER[a.severity] ?? 3) - (SEVERITY_ORDER[b.severity] ?? 3);
      }
      if (field === 'source') return a.source.localeCompare(b.source);
      return a.id.localeCompare(b.id);
    });
  });

  const nodeLookup = createMemo(() => {
    const map: Record<string, string> = {};
    for (const n of nodes()) {
      map[n.id] = n.display_name || n.name;
    }
    return map;
  });

  const severityBadge = (severity: string) => {
    const colors: Record<string, { bg: string; fg: string }> = {
      must: { bg: '#dc2626', fg: '#fef2f2' },
      should: { bg: '#f59e0b', fg: '#451a03' },
      info: { bg: '#64748b', fg: '#f1f5f9' },
    };
    const c = colors[severity] ?? colors.info;
    return (
      <span style={{
        padding: '2px 8px',
        'border-radius': '4px',
        'font-size': '10px',
        'font-weight': '600',
        background: c.bg,
        color: c.fg,
        'text-transform': 'uppercase',
      }}>
        {severity}
      </span>
    );
  };

  const navigateToNode = (nodeId: string) => {
    setSelectedNodeId(nodeId);
    setActiveView('architecture');
  };

  return (
    <div style={{ padding: '24px', overflow: 'auto', height: '100%' }}>
      <div style={{ display: 'flex', 'align-items': 'center', 'justify-content': 'space-between', 'margin-bottom': '20px' }}>
        <h2 style={{ 'font-size': '18px', 'font-weight': '600', color: '#f1f5f9', margin: '0' }}>
          Architecture Guarantees
        </h2>
        <div style={{ display: 'flex', gap: '8px' }}>
          <SortButton label="Severity" field="severity" current={sortField()} onClick={setSortField} />
          <SortButton label="Source" field="source" current={sortField()} onClick={setSortField} />
          <SortButton label="ID" field="id" current={sortField()} onClick={setSortField} />
        </div>
      </div>

      <div style={{ display: 'flex', 'flex-direction': 'column', gap: '8px' }}>
        <For each={sorted()}>
          {(inv) => (
            <div style={{
              background: '#1e293b',
              'border-radius': '8px',
              padding: '14px 16px',
              border: '1px solid #334155',
            }}>
              <div style={{ display: 'flex', 'align-items': 'center', gap: '10px', 'margin-bottom': '8px' }}>
                {severityBadge(inv.severity)}
                <span style={{ 'font-size': '12px', color: '#64748b', 'font-family': 'monospace' }}>
                  {inv.id}
                </span>
                <span style={{
                  'font-size': '11px',
                  color: inv.source === 'claude_md' ? '#a78bfa' : '#64748b',
                  'margin-left': 'auto',
                }}>
                  {inv.source === 'claude_md' ? 'CLAUDE.md' : 'code'}
                </span>
              </div>
              <div style={{ 'font-size': '14px', color: '#e2e8f0', 'line-height': '1.5' }}>
                {inv.description}
              </div>
              {inv.related_nodes && inv.related_nodes.length > 0 && (
                <div style={{ display: 'flex', gap: '6px', 'margin-top': '8px', 'flex-wrap': 'wrap' }}>
                  <For each={inv.related_nodes}>
                    {(nodeId) => (
                      <button
                        onClick={() => navigateToNode(nodeId)}
                        style={{
                          padding: '2px 8px',
                          'border-radius': '4px',
                          'font-size': '11px',
                          background: '#0f172a',
                          color: '#7dd3fc',
                          border: '1px solid #1e3a5f',
                          cursor: 'pointer',
                          'font-family': 'monospace',
                        }}
                      >
                        {nodeLookup()[nodeId] ?? nodeId.split('.').pop()}
                      </button>
                    )}
                  </For>
                </div>
              )}
            </div>
          )}
        </For>
      </div>
    </div>
  );
}

function SortButton(props: { label: string; field: SortField; current: SortField; onClick: (f: SortField) => void }) {
  const active = () => props.current === props.field;
  return (
    <button
      onClick={() => props.onClick(props.field)}
      style={{
        padding: '4px 10px',
        'border-radius': '4px',
        'font-size': '12px',
        background: active() ? '#334155' : 'transparent',
        color: active() ? '#e2e8f0' : '#64748b',
        border: active() ? '1px solid #475569' : '1px solid transparent',
        cursor: 'pointer',
      }}
    >
      {props.label}
    </button>
  );
}
