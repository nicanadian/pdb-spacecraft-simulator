import { createSignal, createMemo } from 'solid-js';
import type { ModelGraph, ModelNode, ModelEdge, ModelGroup, ModelInvariant, LayoutNode } from '../types/model';

// Core data
const [graph, setGraph] = createSignal<ModelGraph | null>(null);
const [loading, setLoading] = createSignal(true);
const [error, setError] = createSignal<string | null>(null);

// UI state
const [selectedNodeId, setSelectedNodeId] = createSignal<string | null>(null);
const [activeView, setActiveView] = createSignal<'architecture' | 'guarantees' | 'impact'>('architecture');
const [searchQuery, setSearchQuery] = createSignal('');
const [hiddenGroups, setHiddenGroups] = createSignal<Set<string>>(new Set());
const [impactNodeId, setImpactNodeId] = createSignal<string | null>(null);

// Layout positions (mutable, managed by d3)
const [layoutNodes, setLayoutNodes] = createSignal<LayoutNode[]>([]);

// Derived
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

export {
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
};
