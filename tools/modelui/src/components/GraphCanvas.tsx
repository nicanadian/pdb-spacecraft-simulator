import { createSignal, createEffect, onCleanup, For, Show } from 'solid-js';
import type { LayoutNode, ModelEdge, ModelGroup } from '../types/model';
import { selectedNodeId, setSelectedNodeId, groupLookup } from '../stores/modelStore';

interface Props {
  nodes: LayoutNode[];
  edges: ModelEdge[];
  highlightNodes?: Set<string> | null;
  impactNodeId?: string | null;
}

const KIND_SHAPES: Record<string, string> = {
  component: 'rect',
  data_type: 'diamond',
  enum: 'hexagon',
  interface: 'rect-dashed',
  function: 'circle',
  handler: 'rect',
};

const EDGE_STYLES: Record<string, { dash: string; color: string }> = {
  imports: { dash: '', color: '#475569' },
  lazy_imports: { dash: '4,3', color: '#475569' },
  implements: { dash: '8,4', color: '#22d3ee' },
  registered_in: { dash: '2,4', color: '#a78bfa' },
  uses: { dash: '6,3', color: '#f59e0b' },
  inherits: { dash: '', color: '#22d3ee' },
};

export default function GraphCanvas(props: Props) {
  let svgRef: SVGSVGElement | undefined;
  const [transform, setTransform] = createSignal({ x: 0, y: 0, k: 1 });
  const [dragging, setDragging] = createSignal(false);
  const [dragStart, setDragStart] = createSignal({ x: 0, y: 0 });
  const [size, setSize] = createSignal({ width: 800, height: 600 });

  // Observe container size + register non-passive wheel handler
  createEffect(() => {
    if (!svgRef) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setSize({ width: entry.contentRect.width, height: entry.contentRect.height });
      }
    });
    observer.observe(svgRef);

    // Must add wheel listener as non-passive to allow preventDefault
    svgRef.addEventListener('wheel', handleWheel, { passive: false });

    onCleanup(() => {
      observer.disconnect();
      svgRef?.removeEventListener('wheel', handleWheel);
    });
  });

  // Auto-fit on first load
  createEffect(() => {
    const ns = props.nodes;
    if (ns.length === 0) return;
    const { width, height } = size();
    if (width === 0) return;

    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (const n of ns) {
      if (n.x < minX) minX = n.x;
      if (n.x > maxX) maxX = n.x;
      if (n.y < minY) minY = n.y;
      if (n.y > maxY) maxY = n.y;
    }
    const dataWidth = maxX - minX + 200;
    const dataHeight = maxY - minY + 200;
    const k = Math.min(width / dataWidth, height / dataHeight, 1.5);
    const cx = (minX + maxX) / 2;
    const cy = (minY + maxY) / 2;
    setTransform({ x: width / 2 - cx * k, y: height / 2 - cy * k, k });
  });

  const handleWheel = (e: WheelEvent) => {
    e.preventDefault();
    const t = transform();
    const factor = e.deltaY > 0 ? 0.9 : 1.1;
    const newK = Math.max(0.1, Math.min(5, t.k * factor));
    const rect = svgRef!.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    setTransform({
      x: mx - (mx - t.x) * (newK / t.k),
      y: my - (my - t.y) * (newK / t.k),
      k: newK,
    });
  };

  const handleMouseDown = (e: MouseEvent) => {
    if (e.button !== 0) return;
    setDragging(true);
    setDragStart({ x: e.clientX - transform().x, y: e.clientY - transform().y });
  };

  const handleMouseMove = (e: MouseEvent) => {
    if (!dragging()) return;
    const ds = dragStart();
    setTransform(prev => ({ ...prev, x: e.clientX - ds.x, y: e.clientY - ds.y }));
  };

  const handleMouseUp = () => setDragging(false);

  const nodeColor = (node: LayoutNode) => {
    const g = groupLookup()[node.group];
    return g?.color ?? '#64748b';
  };

  const isHighlighted = (nodeId: string) => {
    if (!props.highlightNodes) return false;
    return props.highlightNodes.has(nodeId);
  };

  const isSelected = (nodeId: string) => selectedNodeId() === nodeId;
  const isImpactCenter = (nodeId: string) => props.impactNodeId === nodeId;

  return (
    <svg
      ref={svgRef}
      style={{ width: '100%', height: '100%', cursor: dragging() ? 'grabbing' : 'grab' }}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
    >
      <defs>
        <marker id="arrow" viewBox="0 0 10 6" refX="10" refY="3" markerWidth="8" markerHeight="6" orient="auto">
          <path d="M0,0 L10,3 L0,6" fill="#475569" />
        </marker>
        <marker id="arrow-highlight" viewBox="0 0 10 6" refX="10" refY="3" markerWidth="8" markerHeight="6" orient="auto">
          <path d="M0,0 L10,3 L0,6" fill="#22d3ee" />
        </marker>
      </defs>

      <g transform={`translate(${transform().x},${transform().y}) scale(${transform().k})`}>
        {/* Edges */}
        <For each={props.edges}>
          {(edge) => {
            const sourceNode = () => props.nodes.find(n => n.id === edge.source);
            const targetNode = () => props.nodes.find(n => n.id === edge.target);
            const style = EDGE_STYLES[edge.relation] ?? EDGE_STYLES.imports;
            const highlighted = () =>
              props.highlightNodes &&
              (props.highlightNodes.has(edge.source) || props.highlightNodes.has(edge.target));

            return (
              <Show when={sourceNode() && targetNode()}>
                <line
                  x1={sourceNode()!.x}
                  y1={sourceNode()!.y}
                  x2={targetNode()!.x}
                  y2={targetNode()!.y}
                  stroke={highlighted() ? '#22d3ee' : style.color}
                  stroke-width={highlighted() ? 1.5 : 0.8}
                  stroke-dasharray={style.dash}
                  opacity={props.highlightNodes && !highlighted() ? 0.15 : 0.5}
                  marker-end={highlighted() ? 'url(#arrow-highlight)' : 'url(#arrow)'}
                />
              </Show>
            );
          }}
        </For>

        {/* Nodes */}
        <For each={props.nodes}>
          {(node) => {
            const color = () => nodeColor(node);
            const highlighted = () => isHighlighted(node.id);
            const selected = () => isSelected(node.id);
            const center = () => isImpactCenter(node.id);
            const dimmed = () => props.highlightNodes != null && !highlighted() && !selected() && !center();
            const r = node.kind === 'function' ? 20 : 0;

            return (
              <g
                transform={`translate(${node.x},${node.y})`}
                onClick={(e) => { e.stopPropagation(); setSelectedNodeId(node.id); }}
                style={{ cursor: 'pointer' }}
                opacity={dimmed() ? 0.2 : 1}
              >
                {/* Shape */}
                {node.kind === 'function' ? (
                  <circle
                    r={20}
                    fill={color() + '33'}
                    stroke={selected() || center() ? '#f1f5f9' : color()}
                    stroke-width={selected() || center() ? 2.5 : 1.5}
                  />
                ) : node.kind === 'enum' ? (
                  <polygon
                    points="-24,0 -12,-16 12,-16 24,0 12,16 -12,16"
                    fill={color() + '33'}
                    stroke={selected() || center() ? '#f1f5f9' : color()}
                    stroke-width={selected() || center() ? 2.5 : 1.5}
                  />
                ) : (
                  <rect
                    x={-40}
                    y={-14}
                    width={80}
                    height={28}
                    rx={4}
                    fill={color() + '33'}
                    stroke={selected() || center() ? '#f1f5f9' : color()}
                    stroke-width={selected() || center() ? 2.5 : 1.5}
                    stroke-dasharray={node.kind === 'interface' ? '4,2' : ''}
                  />
                )}
                {/* Label */}
                <text
                  text-anchor="middle"
                  dominant-baseline="central"
                  fill={selected() ? '#f1f5f9' : '#cbd5e1'}
                  font-size="10"
                  font-family="Inter, sans-serif"
                >
                  {(node.display_name || node.name).slice(0, 14)}
                </text>
              </g>
            );
          }}
        </For>
      </g>
    </svg>
  );
}
