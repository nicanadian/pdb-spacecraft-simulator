import { Show, For } from 'solid-js';
import { selectedNode, setSelectedNodeId, groupLookup, edges } from '../stores/modelStore';

export default function NodeDetail() {
  const node = selectedNode;
  const group = () => {
    const n = node();
    return n ? groupLookup()[n.group] : null;
  };

  const incomingEdges = () => {
    const n = node();
    if (!n) return [];
    return edges().filter(e => e.target === n.id);
  };

  const outgoingEdges = () => {
    const n = node();
    if (!n) return [];
    return edges().filter(e => e.source === n.id);
  };

  return (
    <Show when={node()}>
      {(n) => (
        <div style={{
          width: '320px',
          background: '#1e293b',
          'border-left': '1px solid #334155',
          overflow: 'auto',
          padding: '16px',
          'flex-shrink': '0',
        }}>
          {/* Header */}
          <div style={{ display: 'flex', 'justify-content': 'space-between', 'align-items': 'flex-start', 'margin-bottom': '16px' }}>
            <div>
              <div style={{ 'font-size': '16px', 'font-weight': '600', color: '#f1f5f9' }}>
                {n().display_name || n().name}
              </div>
              <div style={{ 'font-size': '12px', color: '#64748b', 'margin-top': '2px', 'font-family': 'monospace' }}>
                {n().id}
              </div>
            </div>
            <button
              onClick={() => setSelectedNodeId(null)}
              style={{
                background: 'transparent',
                border: 'none',
                color: '#94a3b8',
                cursor: 'pointer',
                'font-size': '18px',
                padding: '0 4px',
              }}
            >
              &times;
            </button>
          </div>

          {/* Kind + Group badges */}
          <div style={{ display: 'flex', gap: '6px', 'margin-bottom': '12px', 'flex-wrap': 'wrap' }}>
            <span style={{
              padding: '2px 8px',
              'border-radius': '4px',
              'font-size': '11px',
              background: '#334155',
              color: '#e2e8f0',
            }}>
              {n().kind}
            </span>
            <Show when={group()}>
              {(g) => (
                <span style={{
                  padding: '2px 8px',
                  'border-radius': '4px',
                  'font-size': '11px',
                  background: g().color + '22',
                  color: g().color,
                  border: `1px solid ${g().color}44`,
                }}>
                  {g().name}
                </span>
              )}
            </Show>
          </div>

          {/* Description / docstring */}
          <Show when={n().description || n().docstring}>
            <div style={{
              'font-size': '13px',
              color: '#94a3b8',
              'margin-bottom': '16px',
              'line-height': '1.5',
            }}>
              {n().description || n().docstring}
            </div>
          </Show>

          {/* File location */}
          <Show when={n().file_path}>
            <div style={{ 'font-size': '12px', color: '#64748b', 'margin-bottom': '16px', 'font-family': 'monospace' }}>
              {n().file_path}{n().line_number ? `:${n().line_number}` : ''}
            </div>
          </Show>

          {/* Fields */}
          <Show when={n().fields && n().fields!.length > 0}>
            <Section title="Fields">
              <For each={n().fields}>
                {(field) => (
                  <div style={{ 'font-size': '12px', 'font-family': 'monospace', padding: '2px 0', color: '#cbd5e1' }}>
                    <span style={{ color: '#7dd3fc' }}>{field.name}</span>
                    <Show when={field.type}>
                      <span style={{ color: '#64748b' }}>: {field.type}</span>
                    </Show>
                  </div>
                )}
              </For>
            </Section>
          </Show>

          {/* Methods */}
          <Show when={n().methods && n().methods!.length > 0}>
            <Section title="Methods">
              <For each={n().methods}>
                {(method) => (
                  <div style={{ 'font-size': '12px', 'font-family': 'monospace', padding: '2px 0', color: '#cbd5e1' }}>
                    <Show when={method.abstract}>
                      <span style={{ color: '#f59e0b', 'font-size': '10px' }}>abstract </span>
                    </Show>
                    <span style={{ color: '#a78bfa' }}>{method.name}</span>
                    <span style={{ color: '#64748b' }}>({(method.params ?? []).join(', ')})</span>
                    <Show when={method.return_type}>
                      <span style={{ color: '#64748b' }}> -&gt; {method.return_type}</span>
                    </Show>
                  </div>
                )}
              </For>
            </Section>
          </Show>

          {/* Edges */}
          <Show when={incomingEdges().length > 0}>
            <Section title={`Incoming (${incomingEdges().length})`}>
              <For each={incomingEdges()}>
                {(edge) => (
                  <EdgeItem
                    nodeId={edge.source}
                    relation={edge.relation}
                    direction="from"
                  />
                )}
              </For>
            </Section>
          </Show>

          <Show when={outgoingEdges().length > 0}>
            <Section title={`Outgoing (${outgoingEdges().length})`}>
              <For each={outgoingEdges()}>
                {(edge) => (
                  <EdgeItem
                    nodeId={edge.target}
                    relation={edge.relation}
                    direction="to"
                  />
                )}
              </For>
            </Section>
          </Show>
        </div>
      )}
    </Show>
  );
}

function Section(props: { title: string; children: any }) {
  return (
    <div style={{ 'margin-bottom': '16px' }}>
      <div style={{
        'font-size': '11px',
        color: '#94a3b8',
        'text-transform': 'uppercase',
        'letter-spacing': '0.05em',
        'margin-bottom': '6px',
      }}>
        {props.title}
      </div>
      {props.children}
    </div>
  );
}

function EdgeItem(props: { nodeId: string; relation: string; direction: string }) {
  const shortName = () => {
    const parts = props.nodeId.split('.');
    return parts[parts.length - 1];
  };

  return (
    <button
      onClick={() => setSelectedNodeId(props.nodeId)}
      style={{
        display: 'block',
        width: '100%',
        'text-align': 'left',
        padding: '4px 8px',
        background: 'transparent',
        border: 'none',
        color: '#7dd3fc',
        'font-size': '12px',
        'font-family': 'monospace',
        cursor: 'pointer',
        'border-radius': '3px',
      }}
    >
      <span style={{ color: '#64748b', 'font-size': '10px' }}>{props.relation} </span>
      {shortName()}
    </button>
  );
}
