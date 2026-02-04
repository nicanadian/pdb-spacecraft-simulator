import type { ModelEdge, ModelInvariant } from '../types/model';

export interface ImpactResult {
  upstream: Set<string>;   // dependencies (what this node depends on)
  downstream: Set<string>; // dependents (what depends on this node)
  affectedInvariants: ModelInvariant[];
}

/**
 * Compute transitive upstream and downstream dependencies for a given node.
 */
export function computeImpact(
  nodeId: string,
  edges: ModelEdge[],
  invariants: ModelInvariant[]
): ImpactResult {
  // Build adjacency lists
  const outgoing: Record<string, string[]> = {};  // source -> targets
  const incoming: Record<string, string[]> = {};  // target -> sources

  for (const edge of edges) {
    if (!outgoing[edge.source]) outgoing[edge.source] = [];
    outgoing[edge.source].push(edge.target);
    if (!incoming[edge.target]) incoming[edge.target] = [];
    incoming[edge.target].push(edge.source);
  }

  // Traverse upstream (what does nodeId depend on)
  const upstream = new Set<string>();
  const upQueue = [nodeId];
  while (upQueue.length > 0) {
    const current = upQueue.pop()!;
    for (const dep of outgoing[current] ?? []) {
      if (!upstream.has(dep) && dep !== nodeId) {
        upstream.add(dep);
        upQueue.push(dep);
      }
    }
  }

  // Traverse downstream (what depends on nodeId)
  const downstream = new Set<string>();
  const downQueue = [nodeId];
  while (downQueue.length > 0) {
    const current = downQueue.pop()!;
    for (const dep of incoming[current] ?? []) {
      if (!downstream.has(dep) && dep !== nodeId) {
        downstream.add(dep);
        downQueue.push(dep);
      }
    }
  }

  // Find affected invariants
  const allAffected = new Set([nodeId, ...upstream, ...downstream]);
  const affectedInvariants = invariants.filter(inv =>
    inv.related_nodes?.some(rn => allAffected.has(rn))
  );

  return { upstream, downstream, affectedInvariants };
}
