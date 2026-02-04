import { createMemo, For, Show } from 'solid-js';
import {
  archNodes, archEdges, collapsedIds, selectedNodeId, setSelectedNodeId,
  requirementLinks, requirementItems,
} from '../stores/modelStore';

/**
 * Interface Contracts view.
 * Shows abstract interfaces (PropagatorInterface, ActivityHandler, etc.)
 * and data contracts (SimConfig, SimResults, etc.) grouped by their parent domain.
 * Uses a grouped card layout instead of a tree since these cut across domains.
 */
export default function InterfaceContractsView() {
  // Collect Interface and DataContract nodes from ALL domains
  const interfaceNodes = createMemo(() =>
    archNodes().filter(n =>
      n.level === 'L3' && (n.arch_type === 'Interface' || n.arch_type === 'DataContract')
    )
  );

  // Group by parent L2 domain
  const groupedByDomain = createMemo(() => {
    const groups: Record<string, { domain: string; interfaces: typeof interfaceNodes extends () => (infer T)[] ? T[] : never; contracts: typeof interfaceNodes extends () => (infer T)[] ? T[] : never }> = {};
    const allNodes = archNodes();
    const byId: Record<string, typeof allNodes[0]> = {};
    for (const n of allNodes) byId[n.id] = n;

    for (const n of interfaceNodes()) {
      const parent = byId[n.parent_id];
      const domainName = parent?.name ?? 'Other';
      if (!groups[domainName]) {
        groups[domainName] = { domain: domainName, interfaces: [], contracts: [] };
      }
      if (n.arch_type === 'Interface') {
        groups[domainName].interfaces.push(n);
      } else {
        groups[domainName].contracts.push(n);
      }
    }

    return Object.values(groups).sort((a, b) => a.domain.localeCompare(b.domain));
  });

  // Edges between interface/contract nodes (implements, uses)
  const relevantEdges = createMemo(() => {
    const ids = new Set(interfaceNodes().map(n => n.id));
    return archEdges().filter(e =>
      e.relation !== 'contains' && (ids.has(e.source) || ids.has(e.target))
    );
  });

  // Requirement links allocated to these nodes
  const reqLinksForNode = (nodeId: string) =>
    requirementLinks().filter(lk => lk.target_id === nodeId && lk.relation === 'allocatedTo');

  return (
    <div style={{ padding: '24px', overflow: 'auto', height: '100%' }}>
      <h2 style={{ 'font-size': '18px', 'font-weight': '600', color: '#f1f5f9', margin: '0 0 8px 0' }}>
        Interface Contracts
      </h2>
      <p style={{ 'font-size': '13px', color: '#64748b', margin: '0 0 24px 0' }}>
        Abstract interfaces and data contracts across all domains
        &middot; {interfaceNodes().length} types
      </p>

      <div style={{ display: 'flex', 'flex-direction': 'column', gap: '20px' }}>
        <For each={groupedByDomain()}>
          {(group) => (
            <div>
              <div style={{
                'font-size': '13px',
                'font-weight': '600',
                color: '#06b6d4',
                'margin-bottom': '10px',
                'text-transform': 'uppercase',
                'letter-spacing': '0.05em',
              }}>
                {group.domain}
              </div>

              <div style={{ display: 'flex', gap: '10px', 'flex-wrap': 'wrap' }}>
                {/* Interfaces */}
                <For each={group.interfaces}>
                  {(node) => <ContractCard node={node} kind="interface" reqCount={reqLinksForNode(node.id).length} />}
                </For>
                {/* Data contracts */}
                <For each={group.contracts}>
                  {(node) => <ContractCard node={node} kind="contract" reqCount={reqLinksForNode(node.id).length} />}
                </For>
              </div>
            </div>
          )}
        </For>
      </div>
    </div>
  );
}

function ContractCard(props: { node: any; kind: 'interface' | 'contract'; reqCount: number }) {
  const selected = () => selectedNodeId() === props.node.id;
  const borderColor = props.kind === 'interface' ? '#22d3ee' : '#a78bfa';
  const label = props.kind === 'interface' ? 'INTERFACE' : 'DATA';

  return (
    <div
      onClick={() => setSelectedNodeId(props.node.id)}
      style={{
        padding: '12px 16px',
        'border-radius': '8px',
        background: selected() ? '#334155' : '#1e293b',
        border: `1px solid ${selected() ? borderColor : '#334155'}`,
        'border-left': `3px solid ${borderColor}`,
        cursor: 'pointer',
        'min-width': '180px',
        'max-width': '280px',
      }}
    >
      <div style={{ display: 'flex', 'align-items': 'center', gap: '8px', 'margin-bottom': '4px' }}>
        <span style={{
          'font-size': '9px',
          'font-weight': '700',
          color: borderColor,
          'letter-spacing': '0.05em',
        }}>
          {label}
        </span>
        <Show when={props.reqCount > 0}>
          <span style={{
            'font-size': '9px',
            padding: '1px 5px',
            'border-radius': '3px',
            background: '#7c3aed',
            color: '#fff',
          }}>
            {props.reqCount} REQ
          </span>
        </Show>
      </div>
      <div style={{ 'font-size': '13px', color: '#e2e8f0', 'font-weight': '500' }}>
        {props.node.name}
      </div>
      <Show when={props.node.description}>
        <div style={{ 'font-size': '11px', color: '#64748b', 'margin-top': '4px', 'line-height': '1.4' }}>
          {(props.node.description as string).slice(0, 80)}
        </div>
      </Show>
    </div>
  );
}
