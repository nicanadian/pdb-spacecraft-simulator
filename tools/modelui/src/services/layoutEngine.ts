import {
  forceSimulation,
  forceLink,
  forceManyBody,
  forceCenter,
  forceCollide,
  type SimulationNodeDatum,
  type SimulationLinkDatum,
} from 'd3-force';
import type { ModelNode, ModelEdge, LayoutNode } from '../types/model';

interface LinkDatum extends SimulationLinkDatum<LayoutNode> {
  source: string | LayoutNode;
  target: string | LayoutNode;
  relation: string;
}

export function computeLayout(
  nodes: ModelNode[],
  edges: ModelEdge[],
  width: number,
  height: number,
  onTick?: (nodes: LayoutNode[]) => void
): { stop: () => void } {
  const layoutNodes: LayoutNode[] = nodes.map(n => ({
    ...n,
    x: Math.random() * width - width / 2,
    y: Math.random() * height - height / 2,
  }));

  const nodeIds = new Set(nodes.map(n => n.id));
  const links: LinkDatum[] = edges
    .filter(e => nodeIds.has(e.source) && nodeIds.has(e.target))
    .map(e => ({
      source: e.source,
      target: e.target,
      relation: e.relation,
    }));

  const simulation = forceSimulation<LayoutNode>(layoutNodes)
    .force('link', forceLink<LayoutNode, LinkDatum>(links)
      .id(d => d.id)
      .distance(d => d.relation === 'implements' ? 80 : 120)
      .strength(d => d.relation === 'implements' ? 0.8 : 0.3)
    )
    .force('charge', forceManyBody<LayoutNode>().strength(-300).distanceMax(500))
    .force('center', forceCenter(0, 0))
    .force('collide', forceCollide<LayoutNode>().radius(30).strength(0.7))
    .alphaDecay(0.02)
    .on('tick', () => {
      if (onTick) {
        onTick([...layoutNodes]);
      }
    });

  // Run synchronous ticks for initial layout
  simulation.tick(150);
  if (onTick) {
    onTick([...layoutNodes]);
  }

  return {
    stop: () => simulation.stop(),
  };
}
