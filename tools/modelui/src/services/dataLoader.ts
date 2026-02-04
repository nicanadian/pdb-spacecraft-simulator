import type { ModelGraph } from '../types/model';

export async function loadModelGraph(): Promise<ModelGraph> {
  const resp = await fetch('./model.json');
  if (!resp.ok) {
    throw new Error(`Failed to load model.json: ${resp.status} ${resp.statusText}`);
  }
  return resp.json();
}
