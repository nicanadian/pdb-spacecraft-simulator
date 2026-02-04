import { createSignal, createMemo, createEffect } from 'solid-js';
import type {
  ModelGraph, ModelNode, ModelEdge, ModelGroup, ModelInvariant, LayoutNode,
  ArchModelGraph, ArchNode, ArchEdge, ArchLevel, ViewId, ViewpointDef,
  Requirement, RequirementLink,
} from '../types/model';

// Core data
const [graph, setGraph] = createSignal<ModelGraph | null>(null);
const [loading, setLoading] = createSignal(true);
const [error, setError] = createSignal<string | null>(null);

// v2 architecture model
const [archModel, setArchModel] = createSignal<ArchModelGraph | null>(null);

// UI state
const [selectedNodeId, setSelectedNodeId] = createSignal<string | null>(null);
const [activeView, setActiveView] = createSignal<'architecture' | 'guarantees' | 'impact'>('architecture');
const [activeViewpoint, _setActiveViewpoint] = createSignal<ViewId>('capability-map');
const [searchQuery, setSearchQuery] = createSignal('');
const [hiddenGroups, setHiddenGroups] = createSignal<Set<string>>(new Set());
const [impactNodeId, setImpactNodeId] = createSignal<string | null>(null);
// expandedNodes: set of node IDs the user has explicitly expanded.
// Nodes with children start COLLAPSED unless in this set.
const [expandedNodes, setExpandedNodes] = createSignal<Set<string>>(new Set());
const [activeLevel, setActiveLevel] = createSignal<ArchLevel>('L1');
const [requirementOverlay, setRequirementOverlay] = createSignal(false);
const [focusNodeId, setFocusNodeId] = createSignal<string | null>(null);

// When switching viewpoints, reset expanded nodes to L0+L1 only (so L2 domains are visible)
function setActiveViewpoint(vp: ViewId) {
  _setActiveViewpoint(vp);
  // Auto-expand L0 and L1 nodes so the top two levels are visible
  const model = archModel();
  if (model) {
    const autoExpand = new Set<string>();
    for (const n of model.architecture.nodes) {
      if (n.level === 'L0' || n.level === 'L1') {
        autoExpand.add(n.id);
      }
    }
    setExpandedNodes(autoExpand);
  }
}

// Layout positions (mutable, managed by d3)
const [layoutNodes, setLayoutNodes] = createSignal<LayoutNode[]>([]);

// Derived: legacy v1
const nodes = createMemo(() => graph()?.nodes ?? []);
const edges = createMemo(() => graph()?.edges ?? []);
const groups = createMemo(() => graph()?.groups ?? []);
const invariants = createMemo(() => graph()?.invariants ?? []);

const selectedNode = createMemo(() => {
  const id = selectedNodeId();
  if (!id) return null;
  return nodes().find(n => n.id === id) ?? null;
});

const visibleNodes = createMemo(() => {
  const hidden = hiddenGroups();
  const query = searchQuery().toLowerCase();
  return nodes().filter(n => {
    if (hidden.has(n.group)) return false;
    if (query && !n.name.toLowerCase().includes(query) && !n.id.toLowerCase().includes(query)) {
      return false;
    }
    return true;
  });
});

const visibleEdges = createMemo(() => {
  const visIds = new Set(visibleNodes().map(n => n.id));
  return edges().filter(e => visIds.has(e.source) && visIds.has(e.target));
});

const groupLookup = createMemo(() => {
  const lookup: Record<string, ModelGroup> = {};
  for (const g of groups()) {
    lookup[g.id] = g;
  }
  return lookup;
});

// Derived: v2 architecture
const archNodes = createMemo(() => archModel()?.architecture?.nodes ?? []);
const archEdges = createMemo(() => archModel()?.architecture?.edges ?? []);
const requirementItems = createMemo(() => archModel()?.requirements?.items ?? []);
const requirementLinks = createMemo(() => archModel()?.requirements?.links ?? []);
const viewpoints = createMemo(() => archModel()?.viewpoints ?? []);

// Arch nodes filtered by current viewpoint
const viewpointArchNodes = createMemo(() => {
  const model = archModel();
  if (!model) return [];
  const vp = model.viewpoints.find(v => v.id === activeViewpoint());
  if (!vp) return archNodes();
  const layers = new Set(vp.include_layers);
  let filtered = model.architecture.nodes.filter(n => layers.has(n.level));
  if (vp.domain) {
    filtered = filtered.filter(n => !n.domain || n.domain === vp.domain);
  }
  return filtered;
});

// Arch edges filtered by current viewpoint
const viewpointArchEdges = createMemo(() => {
  const model = archModel();
  if (!model) return [];
  const vp = model.viewpoints.find(v => v.id === activeViewpoint());
  const nodeIds = new Set(viewpointArchNodes().map(n => n.id));
  let filtered = model.architecture.edges.filter(
    e => nodeIds.has(e.source) && nodeIds.has(e.target)
  );
  if (vp?.connector_types && vp.connector_types.length > 0) {
    const types = new Set(vp.connector_types);
    // Always include 'contains'
    types.add('contains');
    filtered = filtered.filter(e => types.has(e.relation));
  }
  return filtered;
});

// Compute collapsedIds from expandedNodes (inverted logic):
// A node is collapsed if it has children AND is NOT in expandedNodes.
const collapsedIds = createMemo(() => {
  const expanded = expandedNodes();
  const collapsed = new Set<string>();
  for (const n of archNodes()) {
    if (n.children && n.children.length > 0 && !expanded.has(n.id)) {
      collapsed.add(n.id);
    }
  }
  return collapsed;
});

// Hierarchy tree for nav sidebar (L0 -> L1 -> L2 -> L3)
interface HierarchyTreeNode {
  id: string;
  name: string;
  level: ArchLevel;
  children: HierarchyTreeNode[];
  archNode: ArchNode;
}

const hierarchyTree = createMemo((): HierarchyTreeNode[] => {
  const all = archNodes();
  if (all.length === 0) return [];

  const treeNodes: Record<string, HierarchyTreeNode> = {};
  for (const n of all) {
    if (n.level === 'L4') continue; // Skip L4 in nav
    treeNodes[n.id] = { id: n.id, name: n.name, level: n.level, children: [], archNode: n };
  }

  const roots: HierarchyTreeNode[] = [];
  for (const n of all) {
    if (n.level === 'L4') continue;
    const tn = treeNodes[n.id];
    if (n.parent_id && treeNodes[n.parent_id]) {
      treeNodes[n.parent_id].children.push(tn);
    } else if (!n.parent_id || !treeNodes[n.parent_id]) {
      roots.push(tn);
    }
  }

  return roots;
});

// Requirements for currently focused/selected scope
const scopedRequirements = createMemo(() => {
  const model = archModel();
  if (!model) return [];
  const focus = focusNodeId();
  if (!focus) return model.requirements.items;
  const links = model.requirements.links.filter(lk => lk.target_id === focus);
  const reqIds = new Set(links.map(lk => lk.requirement_id));
  return model.requirements.items.filter(r => reqIds.has(r.id));
});

// Segments (from archModel L1 nodes or synthesized from groups)
const segments = createMemo(() => {
  const model = archModel();
  if (model) {
    return model.architecture.nodes
      .filter(n => n.level === 'L1')
      .map(n => ({
        id: n.id,
        name: n.name,
        color: (n.metadata?.color as string) ?? '#64748b',
        description: n.description,
        children: n.children,
      }));
  }
  // Fallback: synthesize from groups
  return groups().map(g => ({
    id: g.id,
    name: g.name,
    color: g.color,
    description: g.description ?? '',
    children: [] as string[],
  }));
});

// Whether we have v2 arch data
const hasArchModel = createMemo(() => archModel() !== null);

function toggleGroup(groupId: string) {
  setHiddenGroups(prev => {
    const next = new Set(prev);
    if (next.has(groupId)) {
      next.delete(groupId);
    } else {
      next.add(groupId);
    }
    return next;
  });
}

function toggleExpanded(nodeId: string) {
  setExpandedNodes(prev => {
    const next = new Set(prev);
    if (next.has(nodeId)) {
      next.delete(nodeId);
    } else {
      next.add(nodeId);
    }
    return next;
  });
}

// On initial arch model load, auto-expand L0+L1
createEffect(() => {
  const model = archModel();
  if (!model) return;
  const autoExpand = new Set<string>();
  for (const n of model.architecture.nodes) {
    if (n.level === 'L0' || n.level === 'L1') {
      autoExpand.add(n.id);
    }
  }
  setExpandedNodes(autoExpand);
});

export {
  // v1 core
  graph, setGraph,
  loading, setLoading,
  error, setError,
  selectedNodeId, setSelectedNodeId,
  activeView, setActiveView,
  searchQuery, setSearchQuery,
  hiddenGroups, setHiddenGroups,
  impactNodeId, setImpactNodeId,
  layoutNodes, setLayoutNodes,
  nodes, edges, groups, invariants,
  selectedNode,
  visibleNodes, visibleEdges,
  groupLookup,
  toggleGroup,
  // v2 architecture
  archModel, setArchModel,
  activeViewpoint, setActiveViewpoint,
  expandedNodes, setExpandedNodes,
  collapsedIds,
  activeLevel, setActiveLevel,
  requirementOverlay, setRequirementOverlay,
  focusNodeId, setFocusNodeId,
  archNodes, archEdges,
  requirementItems, requirementLinks,
  viewpoints,
  viewpointArchNodes, viewpointArchEdges,
  hierarchyTree,
  scopedRequirements,
  segments,
  hasArchModel,
  toggleExpanded,
};

export type { HierarchyTreeNode };
