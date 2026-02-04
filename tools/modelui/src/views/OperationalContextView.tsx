import { createMemo, For, Show } from 'solid-js';
import {
  archModel, setActiveViewpoint, setSelectedNodeId, selectedNodeId,
} from '../stores/modelStore';
import type { ArchNode } from '../types/model';

export default function OperationalContextView() {
  const model = archModel;

  const enterprise = createMemo(() =>
    model()?.architecture.nodes.find(n => n.arch_type === 'Enterprise') ?? null
  );

  const externalActors = createMemo(() =>
    model()?.architecture.nodes.filter(n =>
      n.level === 'L0' && (n.arch_type === 'ExternalActor' || n.arch_type === 'ExternalSystem')
    ) ?? []
  );

  const operationalDomains = createMemo(() =>
    model()?.architecture.nodes.filter(n =>
      n.level === 'L2' && n.domain === 'Operational'
    ) ?? []
  );

  return (
    <div style={{ width: '100%', height: '100%', display: 'flex', 'flex-direction': 'column', 'align-items': 'center', 'justify-content': 'center', padding: '40px', gap: '32px' }}>
      {/* External Actors row */}
      <div style={{ display: 'flex', gap: '16px', 'flex-wrap': 'wrap', 'justify-content': 'center' }}>
        <For each={externalActors()}>
          {(actor) => (
            <ContextBox
              node={actor}
              color={actor.arch_type === 'ExternalSystem' ? '#06b6d4' : '#f59e0b'}
              icon={actor.arch_type === 'ExternalSystem' ? 'SYS' : 'ACT'}
            />
          )}
        </For>
      </div>

      {/* System boundary */}
      <Show when={enterprise()}>
        {(ent) => (
          <div
            onClick={() => setActiveViewpoint('capability-map')}
            style={{
              border: '2px solid #334155',
              'border-radius': '12px',
              padding: '24px',
              'min-width': '500px',
              cursor: 'pointer',
              background: '#1e293b',
              'text-align': 'center',
            }}
          >
            <div style={{ 'font-size': '16px', 'font-weight': '600', color: '#f1f5f9', 'margin-bottom': '8px' }}>
              {ent().name}
            </div>
            <div style={{ 'font-size': '12px', color: '#94a3b8', 'margin-bottom': '16px' }}>
              {ent().description}
            </div>
            {/* Operational domains inside */}
            <div style={{ display: 'flex', gap: '12px', 'flex-wrap': 'wrap', 'justify-content': 'center' }}>
              <For each={operationalDomains()}>
                {(dom) => (
                  <div
                    onClick={(e) => { e.stopPropagation(); setSelectedNodeId(dom.id); }}
                    style={{
                      padding: '8px 16px',
                      'border-radius': '6px',
                      background: selectedNodeId() === dom.id ? '#334155' : '#0f172a',
                      border: '1px solid #334155',
                      color: '#cbd5e1',
                      'font-size': '12px',
                      cursor: 'pointer',
                    }}
                  >
                    {dom.name}
                  </div>
                )}
              </For>
            </div>
            <div style={{ 'font-size': '11px', color: '#475569', 'margin-top': '12px' }}>
              Click to explore capabilities
            </div>
          </div>
        )}
      </Show>
    </div>
  );
}

function ContextBox(props: { node: ArchNode; color: string; icon: string }) {
  const selected = () => selectedNodeId() === props.node.id;
  return (
    <div
      onClick={() => setSelectedNodeId(props.node.id)}
      style={{
        padding: '14px 20px',
        'border-radius': '8px',
        background: selected() ? props.color + '22' : '#1e293b',
        border: `1px solid ${selected() ? props.color : '#334155'}`,
        cursor: 'pointer',
        'text-align': 'center',
        'min-width': '120px',
      }}
    >
      <div style={{ 'font-size': '10px', 'font-weight': '600', color: props.color, 'margin-bottom': '4px' }}>
        {props.icon}
      </div>
      <div style={{ 'font-size': '13px', color: '#e2e8f0' }}>
        {props.node.name}
      </div>
      <div style={{ 'font-size': '11px', color: '#64748b', 'margin-top': '2px' }}>
        {props.node.metadata?.interface_type as string ?? ''}
      </div>
    </div>
  );
}
