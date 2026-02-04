import { createSignal, createEffect, onCleanup, For, Show } from 'solid-js';
import type { SwimlaneResult } from '../services/swimlaneLayout';
import { selectedNodeId, setSelectedNodeId, requirementOverlay, requirementLinks } from '../stores/modelStore';

interface Props {
  layout: SwimlaneResult;
}

export default function SwimlaneCanvas(props: Props) {
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
    const { totalWidth, totalHeight } = props.layout;
    if (totalWidth === 0) return;
    const { width, height } = size();
    if (width === 0) return;
    const k = Math.min(width / (totalWidth + 40), height / (totalHeight + 40), 1.5);
    setTransform({ x: (width - totalWidth * k) / 2, y: 20 * k, k });
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

  // Count requirements per node
  const reqCounts = () => {
    const counts: Record<string, number> = {};
    for (const lk of requirementLinks()) {
      if (lk.relation === 'allocatedTo') {
        counts[lk.target_id] = (counts[lk.target_id] ?? 0) + 1;
      }
    }
    return counts;
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
      <g transform={`translate(${transform().x},${transform().y}) scale(${transform().k})`}>
        {/* Columns */}
        <For each={props.layout.columns}>
          {(col) => (
            <g>
              {/* Column background */}
              <rect
                x={col.x}
                y={0}
                width={col.width}
                height={props.layout.totalHeight}
                rx={8}
                fill={col.color + '0a'}
                stroke={col.color + '33'}
                stroke-width="1"
              />
              {/* Column header */}
              <text
                x={col.x + col.width / 2}
                y={24}
                fill={col.color}
                font-size="13"
                font-weight="600"
                text-anchor="middle"
              >
                {col.name}
              </text>

              {/* Domain nodes */}
              <For each={col.nodes}>
                {(node) => {
                  const selected = () => selectedNodeId() === node.id;
                  const rc = () => reqCounts()[node.id] ?? 0;
                  return (
                    <g
                      onClick={(e) => { e.stopPropagation(); setSelectedNodeId(node.id); }}
                      style={{ cursor: 'pointer' }}
                    >
                      <rect
                        x={node.x}
                        y={node.y}
                        width={node.width}
                        height={node.height}
                        rx={6}
                        fill={selected() ? col.color + '33' : col.color + '18'}
                        stroke={selected() ? '#f1f5f9' : col.color + '55'}
                        stroke-width={selected() ? 2 : 1}
                      />
                      <text
                        x={node.x + 10}
                        y={node.y + node.height / 2}
                        fill="#e2e8f0"
                        font-size="12"
                        dominant-baseline="central"
                      >
                        {node.name}
                      </text>
                      {/* Child count badge */}
                      <Show when={node.childCount > 0}>
                        <text
                          x={node.x + node.width - 10}
                          y={node.y + node.height / 2}
                          fill="#64748b"
                          font-size="10"
                          text-anchor="end"
                          dominant-baseline="central"
                        >
                          {node.childCount}
                        </text>
                      </Show>
                      {/* Requirement badge */}
                      <Show when={requirementOverlay() && rc() > 0}>
                        <circle
                          cx={node.x + node.width - 4}
                          cy={node.y + 4}
                          r={8}
                          fill="#7c3aed"
                        />
                        <text
                          x={node.x + node.width - 4}
                          y={node.y + 4}
                          fill="#fff"
                          font-size="8"
                          text-anchor="middle"
                          dominant-baseline="central"
                        >
                          {rc()}
                        </text>
                      </Show>
                    </g>
                  );
                }}
              </For>
            </g>
          )}
        </For>

        {/* Inter-column edges */}
        <For each={props.layout.edges}>
          {(edge) => {
            const dx = edge.target.x - edge.source.x;
            const cp1x = edge.source.x + dx * 0.4;
            const cp2x = edge.source.x + dx * 0.6;
            return (
              <path
                d={`M${edge.source.x},${edge.source.y} C${cp1x},${edge.source.y} ${cp2x},${edge.target.y} ${edge.target.x},${edge.target.y}`}
                fill="none"
                stroke="#475569"
                stroke-width="1"
                stroke-dasharray="4,3"
                opacity="0.4"
              />
            );
          }}
        </For>
      </g>
    </svg>
  );
}
