/**
 * Tree layout engine using d3-hierarchy.
 * Supports top-down (logical view) and left-right (requirements view).
 */
import { hierarchy, tree } from 'd3-hierarchy';
import type { ArchNode, ArchLevel, TreeLayoutNode } from '../types/model';

interface TreeInput {
  id: string;
  name: string;
  level: ArchLevel;
  children: TreeInput[];
  archNode?: ArchNode;
  color: string;
}

export type TreeDirection = 'top-down' | 'left-right';

const LEVEL_COLORS: Record<string, string> = {
  L0: '#f59e0b',
  L1: '#ef4444',
  L2: '#06b6d4',
  L3: '#22c55e',
  L4: '#64748b',
};

function getColor(node: ArchNode): string {
  if (node.metadata?.color) return node.metadata.color as string;
  return LEVEL_COLORS[node.level] ?? '#64748b';
}

/**
 * Build a tree from flat arch nodes and compute positions.
 * Nodes NOT in collapsedIds will show their children.
 */
export function computeTreeLayout(
  nodes: ArchNode[],
  collapsedIds: Set<string>,
  direction: TreeDirection = 'top-down',
): TreeLayoutNode[] {
  if (nodes.length === 0) return [];

  // Build parent-child index
  const byId: Record<string, ArchNode> = {};
  for (const n of nodes) byId[n.id] = n;

  // Build tree input — skip children of collapsed nodes
  function buildTree(nodeId: string): TreeInput | null {
    const n = byId[nodeId];
    if (!n) return null;

    const childInputs: TreeInput[] = [];
    if (!collapsedIds.has(nodeId)) {
      for (const childId of n.children ?? []) {
        if (byId[childId]) {
          const child = buildTree(childId);
          if (child) childInputs.push(child);
        }
      }
    }

    return {
      id: n.id,
      name: n.name,
      level: n.level as ArchLevel,
      children: childInputs,
      archNode: n,
      color: getColor(n),
    };
  }

  // Find roots (nodes whose parent is not in the set)
  const nodeIdSet = new Set(nodes.map(n => n.id));
  const roots = nodes.filter(n => !n.parent_id || !nodeIdSet.has(n.parent_id));

  // If multiple roots, create a virtual root
  let rootInput: TreeInput;
  if (roots.length === 1) {
    const built = buildTree(roots[0].id);
    if (!built) return [];
    rootInput = built;
  } else {
    const children: TreeInput[] = [];
    for (const r of roots) {
      const built = buildTree(r.id);
      if (built) children.push(built);
    }
    rootInput = {
      id: '__root__',
      name: '',
      level: 'L0',
      children,
      color: 'transparent',
    };
  }

  // Create d3 hierarchy
  const root = hierarchy(rootInput, d => d.children);

  // Adaptive spacing based on visible node count
  const visibleCount = root.descendants().length;
  const nodeW = direction === 'top-down'
    ? Math.max(170, Math.min(220, 2000 / Math.max(visibleCount, 1)))
    : 80;
  const nodeH = direction === 'top-down' ? 80 : 200;

  const treeLayout = tree<TreeInput>().nodeSize([nodeW, nodeH]);
  treeLayout(root);

  // Flatten to TreeLayoutNode[]
  const result: TreeLayoutNode[] = [];
  const NODE_WIDTH = 160;
  const NODE_HEIGHT = 44;

  root.each(d => {
    if (d.data.id === '__root__') return;
    const x = direction === 'top-down' ? (d.x ?? 0) : (d.y ?? 0);
    const y = direction === 'top-down' ? (d.y ?? 0) : (d.x ?? 0);
    const isCollapsed = collapsedIds.has(d.data.id);

    result.push({
      id: d.data.id,
      label: d.data.name,
      level: d.data.level,
      x,
      y,
      width: NODE_WIDTH,
      height: NODE_HEIGHT,
      children: [],
      collapsed: isCollapsed,
      color: d.data.color,
      parentId: d.parent?.data.id === '__root__' ? null : (d.parent?.data.id ?? null),
      archNode: d.data.archNode,
    });
  });

  return result;
}
