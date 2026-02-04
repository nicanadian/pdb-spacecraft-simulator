import { createMemo } from 'solid-js';
import TreeCanvas from '../components/TreeCanvas';
import { viewpointArchNodes, viewpointArchEdges, collapsedIds } from '../stores/modelStore';
import { computeTreeLayout } from '../services/treeLayout';

export default function LogicalArchitectureView() {
  const treeNodes = createMemo(() =>
    computeTreeLayout(viewpointArchNodes(), collapsedIds(), 'top-down')
  );

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      <TreeCanvas
        nodes={treeNodes()}
        edges={viewpointArchEdges()}
        direction="top-down"
      />
    </div>
  );
}
