import { createSignal, createEffect, onCleanup, For, Show } from 'solid-js';
import type { TreeLayoutNode, ArchEdge as ArchEdgeType } from '../types/model';
import { selectedNodeId, setSelectedNodeId, toggleExpanded, requirementOverlay, scopedRequirements } from '../stores/modelStore';

interface Props {
  nodes: TreeLayoutNode[];
  edges: ArchEdgeType[];
  direction?: 'top-down' | 'left-right';
}

const LEVEL_COLORS: Record<string, string> = {
  L0: '#f59e0b',
  L1: '#ef4444',
  L2: '#06b6d4',
  L3: '#22c55e',
  L4: '#64748b',
};

export default function TreeCanvas(props: Props) {
  let svgRef: SVGSVGElement | undefined;
  const [transform, setTransform] = createSignal({ x: 0, y: 0, k: 1 });
  const [dragging, setDragging] = createSignal(false);
  const [dragStart, setDragStart] = createSignal({ x: 0, y: 0 });
  const [size, setSize] = createSignal({ width: 800, height: 600 });

  createEffect(() => {
    if (!svgRef) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setSize({ width: entry.contentRect.width, height: entry.contentRect.height });
      }
    });
    observer.observe(svgRef);
    svgRef.addEventListener('wheel', handleWheel, { passive: false });
    onCleanup(() => {
      observer.disconnect();
      svgRef?.removeEventListener('wheel', handleWheel);
    });
  });

  // Auto-fit
  createEffect(() => {
    const ns = props.nodes;
    if (ns.length === 0) return;
    const { width, height } = size();
    if (width === 0) return;

    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (const n of ns) {
      if (n.x - n.width / 2 < minX) minX = n.x - n.width / 2;
      if (n.x + n.width / 2 > maxX) maxX = n.x + n.width / 2;
      if (n.y - n.height / 2 < minY) minY = n.y - n.height / 2;
      if (n.y + n.height / 2 > maxY) maxY = n.y + n.height / 2;
    }
    const dataW = maxX - minX + 100;
    const dataH = maxY - minY + 100;
    const k = Math.min(width / dataW, height / dataH, 1.5);
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

  // Build position lookup for edges
  const nodePositions = () => {
    const map: Record<string, { x: number; y: number }> = {};
    for (const n of props.nodes) {
      map[n.id] = { x: n.x, y: n.y };
    }
    return map;
  };

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
        <marker id="tree-arrow" viewBox="0 0 10 6" refX="10" refY="3" markerWidth="8" markerHeight="6" orient="auto">
          <path d="M0,0 L10,3 L0,6" fill="#475569" />
        </marker>
      </defs>

      <g transform={`translate(${transform().x},${transform().y}) scale(${transform().k})`}>
        {/* Elbow connectors to children */}
        <For each={props.nodes}>
          {(node) => (
            <Show when={node.parentId}>
              {(parentId) => {
                const pPos = () => nodePositions()[parentId()];
                return (
                  <Show when={pPos()}>
                    {(pp) => {
                      const isTopDown = () => (props.direction ?? 'top-down') === 'top-down';
                      return (
                        <path
                          d={isTopDown()
                            ? `M${pp().x},${pp().y + 20} L${pp().x},${(pp().y + 20 + node.y - 20) / 2} L${node.x},${(pp().y + 20 + node.y - 20) / 2} L${node.x},${node.y - 20}`
                            : `M${pp().x + 70},${pp().y} L${(pp().x + 70 + node.x - 70) / 2},${pp().y} L${(pp().x + 70 + node.x - 70) / 2},${node.y} L${node.x - 70},${node.y}`
                          }
                          fill="none"
                          stroke="#334155"
                          stroke-width="1"
                        />
                      );
                    }}
                  </Show>
                );
              }}
            </Show>
          )}
        </For>

        {/* Non-containment edges */}
        <For each={props.edges.filter(e => e.relation !== 'contains')}>
          {(edge) => {
            const src = () => nodePositions()[edge.source];
            const tgt = () => nodePositions()[edge.target];
            return (
              <Show when={src() && tgt()}>
                <line
                  x1={src()!.x}
                  y1={src()!.y}
                  x2={tgt()!.x}
                  y2={tgt()!.y}
                  stroke="#475569"
                  stroke-width="0.8"
                  stroke-dasharray="6,3"
                  opacity="0.5"
                  marker-end="url(#tree-arrow)"
                />
              </Show>
            );
          }}
        </For>

        {/* Nodes */}
        <For each={props.nodes}>
          {(node) => {
            const selected = () => selectedNodeId() === node.id;
            const color = () => node.color || LEVEL_COLORS[node.level] || '#64748b';
            const hasCollapsedChildren = () => node.collapsed && (node.archNode?.children?.length ?? 0) > 0;

            return (
              <g
                transform={`translate(${node.x},${node.y})`}
                onClick={(e) => { e.stopPropagation(); setSelectedNodeId(node.id); }}
                style={{ cursor: 'pointer' }}
              >
                <rect
                  x={-node.width / 2}
                  y={-node.height / 2}
                  width={node.width}
                  height={node.height}
                  rx={6}
                  fill={color() + '22'}
                  stroke={selected() ? '#f1f5f9' : color()}
                  stroke-width={selected() ? 2 : 1.2}
                />
                {/* Level badge */}
                <text
                  x={-node.width / 2 + 8}
                  y={-2}
                  fill={color()}
                  font-size="9"
                  font-weight="600"
                >
                  {node.level}
                </text>
                {/* Label */}
                <text
                  x={-node.width / 2 + 28}
                  y={0}
                  fill={selected() ? '#f1f5f9' : '#cbd5e1'}
                  font-size="11"
                  dominant-baseline="central"
                >
                  {node.label.slice(0, 16)}
                </text>
                {/* Collapse/expand chevron */}
                <Show when={node.archNode?.children && node.archNode.children.length > 0}>
                  <text
                    x={node.width / 2 - 16}
                    y={0}
                    fill="#64748b"
                    font-size="10"
                    dominant-baseline="central"
                    onClick={(e) => { e.stopPropagation(); toggleExpanded(node.id); }}
                    style={{ cursor: 'pointer' }}
                  >
                    {node.collapsed ? '\u25B6' : '\u25BC'}
                  </text>
                </Show>
                {/* +N badge for collapsed */}
                <Show when={hasCollapsedChildren()}>
                  <rect
                    x={node.width / 2 - 6}
                    y={-node.height / 2 - 6}
                    width={20}
                    height={14}
                    rx={7}
                    fill="#475569"
                  />
                  <text
                    x={node.width / 2 + 4}
                    y={-node.height / 2 + 1}
                    fill="#e2e8f0"
                    font-size="9"
                    text-anchor="middle"
                    dominant-baseline="central"
                  >
                    +{node.archNode?.children?.length}
                  </text>
                </Show>
                {/* Requirement overlay badge */}
                <Show when={requirementOverlay()}>
                  {(() => {
                    const reqs = scopedRequirements().filter(r =>
                      r.metadata?.allocated_to === node.id
                    );
                    return reqs.length > 0 ? (
                      <g>
                        <circle
                          cx={node.width / 2 - 4}
                          cy={node.height / 2 - 4}
                          r={8}
                          fill="#7c3aed"
                        />
                        <text
                          x={node.width / 2 - 4}
                          y={node.height / 2 - 4}
                          fill="#fff"
                          font-size="8"
                          text-anchor="middle"
                          dominant-baseline="central"
                        >
                          {reqs.length}
                        </text>
                      </g>
                    ) : null;
                  })()}
                </Show>
              </g>
            );
          }}
        </For>
      </g>
    </svg>
  );
}
