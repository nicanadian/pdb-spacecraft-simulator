import type { ModelGraph, ArchModelGraph } from '../types/model';
import { setGraph, setArchModel } from '../stores/modelStore';

export async function loadModelGraph(): Promise<ModelGraph> {
  const resp = await fetch('./model.json');
  if (!resp.ok) {
    throw new Error(`Failed to load model.json: ${resp.status} ${resp.statusText}`);
  }
  return resp.json();
}

/**
 * Load model data, detecting v1 vs v2 schema and populating the appropriate stores.
 */
export async function loadModelData(): Promise<void> {
  const resp = await fetch('./model.json');
  if (!resp.ok) {
    throw new Error(`Failed to load model.json: ${resp.status} ${resp.statusText}`);
  }
  const data = await resp.json();

  if (data.schema_version === '2.0') {
    // v2 ArchModelGraph
    const archData = data as ArchModelGraph;
    setArchModel(archData);

    // Also populate legacy graph from ir_graph for backward compat
    if (archData.ir_graph) {
      setGraph(archData.ir_graph);
    }
  } else {
    // v1 ModelGraph (or unversioned)
    setGraph(data as ModelGraph);

    // Synthesize minimal arch model from groups as segments
    // so that v1 data can still render in the viewer
    // (the hasArchModel() check will be false, falling back to legacy views)
  }
}
