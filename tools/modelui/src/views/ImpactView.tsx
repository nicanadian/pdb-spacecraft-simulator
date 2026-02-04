import { createSignal, createMemo, createEffect, onCleanup, For, Show } from 'solid-js';
import GraphCanvas from '../components/GraphCanvas';
import {
  visibleNodes, visibleEdges, nodes, edges, invariants,
  setLayoutNodes, layoutNodes, impactNodeId, setImpactNodeId,
} from '../stores/modelStore';
import { computeLayout } from '../services/layoutEngine';
import { computeImpact, type ImpactResult } from '../services/impactAnalysis';
import type { LayoutNode } from '../types/model';

export default function ImpactView() {
  let stopLayout: (() => void) | null = null;

  const impact = createMemo<ImpactResult | null>(() => {
    const id = impactNodeId();
    if (!id) return null;
    return computeImpact(id, edges(), invariants());
  });

  const highlightSet = createMemo(() => {
    const imp = impact();
    const id = impactNodeId();
    if (!imp || !id) return null;
    const set = new Set<string>();
    set.add(id);
    for (const n of imp.upstream) set.add(n);
    for (const n of imp.downstream) set.add(n);
    return set;
  });

  // Layout
  createEffect(() => {
    const ns = visibleNodes();
    const es = visibleEdges();
    if (ns.length === 0) return;
    if (stopLayout) stopLayout();
    const { stop } = computeLayout(ns, es, 1200, 800, (ln: LayoutNode[]) => setLayoutNodes(ln));
    stopLayout = stop;
  });
  onCleanup(() => { if (stopLayout) stopLayout(); });

  return (
    <div style={{ display: 'flex', height: '100%' }}>
      {/* Graph */}
      <div style={{ flex: '1', position: 'relative' }}>
        <GraphCanvas
          nodes={layoutNodes()}
          edges={visibleEdges()}
          highlightNodes={highlightSet()}
          impactNodeId={impactNodeId()}
        />
      </div>

      {/* Side panel */}
      <div style={{
        width: '300px',
        background: '#1e293b',
        'border-left': '1px solid #334155',
        overflow: 'auto',
        padding: '16px',
        'flex-shrink': '0',
      }}>
        <div style={{ 'font-size': '11px', color: '#94a3b8', 'text-transform': 'uppercase', 'letter-spacing': '0.05em', 'margin-bottom': '12px' }}>
          Impact Analysis
        </div>

        {/* Component selector */}
        <select
          value={impactNodeId() ?? ''}
          onChange={(e) => setImpactNodeId(e.currentTarget.value || null)}
          style={{
            width: '100%',
            padding: '8px 12px',
            background: '#0f172a',
            border: '1px solid #334155',
            'border-radius': '6px',
            color: '#e2e8f0',
            'font-size': '13px',
            'margin-bottom': '16px',
          }}
        >
          <option value="">Select a component...</option>
          <For each={nodes().sort((a, b) => a.name.localeCompare(b.name))}>
            {(node) => <option value={node.id}>{node.display_name || node.name}</option>}
          </For>
        </select>

        <Show when={impact()}>
          {(imp) => (
            <>
              {/* Summary */}
              <div style={{ display: 'flex', gap: '8px', 'margin-bottom': '16px' }}>
                <StatBadge label="Upstream" count={imp().upstream.size} color="#06b6d4" />
                <StatBadge label="Downstream" count={imp().downstream.size} color="#f59e0b" />
              </div>

              {/* Upstream list */}
              <Show when={imp().upstream.size > 0}>
                <SectionHeader title={`Dependencies (${imp().upstream.size})`} />
                <NodeList ids={[...imp().upstream]} />
              </Show>

              {/* Downstream list */}
              <Show when={imp().downstream.size > 0}>
                <SectionHeader title={`Dependents (${imp().downstream.size})`} />
                <NodeList ids={[...imp().downstream]} />
              </Show>

              {/* Affected invariants */}
              <Show when={imp().affectedInvariants.length > 0}>
                <SectionHeader title={`Affected Invariants (${imp().affectedInvariants.length})`} />
                <For each={imp().affectedInvariants}>
                  {(inv) => (
                    <div style={{
                      padding: '6px 8px',
                      'margin-bottom': '4px',
                      background: '#0f172a',
                      'border-radius': '4px',
                      'font-size': '12px',
                      color: '#cbd5e1',
                    }}>
                      <span style={{
                        color: inv.severity === 'must' ? '#ef4444' : inv.severity === 'should' ? '#f59e0b' : '#64748b',
                        'font-weight': '600',
                        'font-size': '10px',
                      }}>
                        [{inv.severity.toUpperCase()}]
                      </span>{' '}
                      {inv.description.slice(0, 60)}
                    </div>
                  )}
                </For>
              </Show>
            </>
          )}
        </Show>
      </div>
    </div>
  );
}

function StatBadge(props: { label: string; count: number; color: string }) {
  return (
    <div style={{
      flex: '1',
      padding: '10px',
      background: '#0f172a',
      'border-radius': '6px',
      'text-align': 'center',
    }}>
      <div style={{ 'font-size': '20px', 'font-weight': '600', color: props.color }}>{props.count}</div>
      <div style={{ 'font-size': '11px', color: '#64748b' }}>{props.label}</div>
    </div>
  );
}

function SectionHeader(props: { title: string }) {
  return (
    <div style={{ 'font-size': '11px', color: '#94a3b8', 'text-transform': 'uppercase', 'letter-spacing': '0.05em', 'margin': '12px 0 6px' }}>
      {props.title}
    </div>
  );
}

function NodeList(props: { ids: string[] }) {
  return (
    <div style={{ 'max-height': '150px', overflow: 'auto' }}>
      <For each={props.ids.sort()}>
        {(id) => (
          <div style={{
            padding: '3px 8px',
            'font-size': '11px',
            'font-family': 'monospace',
            color: '#94a3b8',
          }}>
            {id.split('.').pop()}
          </div>
        )}
      </For>
    </div>
  );
}
