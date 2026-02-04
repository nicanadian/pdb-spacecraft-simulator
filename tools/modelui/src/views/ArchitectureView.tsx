import { createEffect, onCleanup, createSignal } from 'solid-js';
import GraphCanvas from '../components/GraphCanvas';
import { visibleNodes, visibleEdges, setLayoutNodes, layoutNodes } from '../stores/modelStore';
import { computeLayout } from '../services/layoutEngine';
import type { LayoutNode } from '../types/model';

export default function ArchitectureView() {
  let stopLayout: (() => void) | null = null;

  createEffect(() => {
    const ns = visibleNodes();
    const es = visibleEdges();
    if (ns.length === 0) return;

    // Stop previous simulation
    if (stopLayout) stopLayout();

    const { stop } = computeLayout(
      ns,
      es,
      1200,
      800,
      (nodes: LayoutNode[]) => setLayoutNodes(nodes),
    );
    stopLayout = stop;
  });

  onCleanup(() => {
    if (stopLayout) stopLayout();
  });

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      <GraphCanvas
        nodes={layoutNodes()}
        edges={visibleEdges()}
      />
      {/* Legend */}
      <div style={{
        position: 'absolute',
        bottom: '16px',
        left: '16px',
        background: 'rgba(15, 23, 42, 0.9)',
        'border-radius': '8px',
        padding: '12px',
        'font-size': '11px',
        color: '#94a3b8',
        display: 'flex',
        gap: '16px',
      }}>
        <div style={{ display: 'flex', 'align-items': 'center', gap: '4px' }}>
          <svg width="20" height="12"><line x1="0" y1="6" x2="20" y2="6" stroke="#475569" stroke-width="1" /></svg>
          imports
        </div>
        <div style={{ display: 'flex', 'align-items': 'center', gap: '4px' }}>
          <svg width="20" height="12"><line x1="0" y1="6" x2="20" y2="6" stroke="#22d3ee" stroke-width="1" stroke-dasharray="8,4" /></svg>
          implements
        </div>
        <div style={{ display: 'flex', 'align-items': 'center', gap: '4px' }}>
          <svg width="20" height="12"><line x1="0" y1="6" x2="20" y2="6" stroke="#475569" stroke-width="1" stroke-dasharray="4,3" /></svg>
          lazy
        </div>
        <div style={{ display: 'flex', 'align-items': 'center', gap: '4px' }}>
          <svg width="20" height="12"><line x1="0" y1="6" x2="20" y2="6" stroke="#f59e0b" stroke-width="1" stroke-dasharray="6,3" /></svg>
          uses
        </div>
      </div>
    </div>
  );
}
