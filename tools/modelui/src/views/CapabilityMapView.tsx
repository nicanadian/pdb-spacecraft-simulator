import { createMemo } from 'solid-js';
import SwimlaneCanvas from '../components/SwimlaneCanvas';
import { viewpointArchNodes, viewpointArchEdges, archNodes } from '../stores/modelStore';
import { computeSwimlaneLayout } from '../services/swimlaneLayout';

export default function CapabilityMapView() {
  const layout = createMemo(() => {
    // For capability map, include L1 + their L2 children
    const l1Nodes = archNodes().filter(n => n.level === 'L1');
    const l2Nodes = archNodes().filter(n => n.level === 'L2');
    const allNodes = [...l1Nodes, ...l2Nodes];
    const allEdges = viewpointArchEdges();
    return computeSwimlaneLayout(allNodes, allEdges);
  });

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      <SwimlaneCanvas layout={layout()} />
    </div>
  );
}
