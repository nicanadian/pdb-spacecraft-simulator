/**
 * Swimlane layout engine for capability-map view.
 * Segments become vertical columns, domain nodes stacked within each column.
 */
import type { ArchNode, ArchEdge, ArchLevel } from '../types/model';

export interface SwimlaneColumn {
  id: string;
  name: string;
  color: string;
  x: number;
  width: number;
  nodes: SwimlaneNode[];
}

export interface SwimlaneNode {
  id: string;
  name: string;
  level: ArchLevel;
  x: number;
  y: number;
  width: number;
  height: number;
  color: string;
  archNode: ArchNode;
  childCount: number;
}

export interface SwimlaneEdge {
  id: string;
  source: { x: number; y: number };
  target: { x: number; y: number };
  relation: string;
}

export interface SwimlaneResult {
  columns: SwimlaneColumn[];
  edges: SwimlaneEdge[];
  totalWidth: number;
  totalHeight: number;
}

const COL_WIDTH = 200;
const COL_GAP = 24;
const NODE_HEIGHT = 44;
const NODE_GAP = 8;
const HEADER_HEIGHT = 48;
const PADDING = 16;

/**
 * Compute swimlane layout from segments (L1) and their domain children (L2).
 */
export function computeSwimlaneLayout(
  allNodes: ArchNode[],
  allEdges: ArchEdge[],
): SwimlaneResult {
  // Gather L1 segments
  const segments = allNodes.filter(n => n.level === 'L1');

  // Index all nodes
  const byId: Record<string, ArchNode> = {};
  for (const n of allNodes) byId[n.id] = n;

  const columns: SwimlaneColumn[] = [];
  const nodePositions: Record<string, { x: number; y: number }> = {};

  let xOffset = PADDING;
  let maxHeight = 0;

  for (const seg of segments) {
    const color = (seg.metadata?.color as string) ?? '#64748b';
    const domainNodes: SwimlaneNode[] = [];

    // Get children (L2 domains)
    const children = (seg.children ?? []).map(id => byId[id]).filter(Boolean);
    let yOffset = HEADER_HEIGHT + PADDING;

    for (const child of children) {
      const childCount = (child.children ?? []).length;
      const nodeX = xOffset + (COL_WIDTH - (COL_WIDTH - 2 * PADDING)) / 2;
      const nodeW = COL_WIDTH - 2 * PADDING;

      domainNodes.push({
        id: child.id,
        name: child.name,
        level: child.level as ArchLevel,
        x: nodeX,
        y: yOffset,
        width: nodeW,
        height: NODE_HEIGHT,
        color,
        archNode: child,
        childCount,
      });

      nodePositions[child.id] = {
        x: nodeX + nodeW / 2,
        y: yOffset + NODE_HEIGHT / 2,
      };

      yOffset += NODE_HEIGHT + NODE_GAP;
    }

    const colHeight = yOffset + PADDING;
    if (colHeight > maxHeight) maxHeight = colHeight;

    columns.push({
      id: seg.id,
      name: seg.name,
      color,
      x: xOffset,
      width: COL_WIDTH,
      nodes: domainNodes,
    });

    xOffset += COL_WIDTH + COL_GAP;
  }

  // Compute inter-column edges
  const edges: SwimlaneEdge[] = [];
  const containsEdges = new Set<string>();
  for (const e of allEdges) {
    if (e.relation === 'contains') containsEdges.add(e.id);
  }

  for (const e of allEdges) {
    if (containsEdges.has(e.id)) continue;
    const srcPos = nodePositions[e.source];
    const tgtPos = nodePositions[e.target];
    if (srcPos && tgtPos && e.source !== e.target) {
      edges.push({
        id: e.id,
        source: srcPos,
        target: tgtPos,
        relation: e.relation,
      });
    }
  }

  return {
    columns,
    edges,
    totalWidth: xOffset - COL_GAP + PADDING,
    totalHeight: maxHeight,
  };
}
