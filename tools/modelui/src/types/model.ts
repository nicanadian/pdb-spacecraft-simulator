/** TypeScript types mirroring the IR JSON schema. */

export interface ModelNode {
  id: string;
  name: string;
  kind: 'component' | 'data_type' | 'enum' | 'interface' | 'function' | 'handler' | 'module';
  group: string;
  module_path?: string;
  file_path?: string;
  line_number?: number;
  docstring?: string;
  display_name?: string;
  description?: string;
  bases?: string[];
  fields?: FieldInfo[];
  methods?: MethodInfo[];
  decorators?: string[];
  metadata?: Record<string, unknown>;
}

export interface FieldInfo {
  name: string;
  type?: string;
  default?: string;
  optional?: boolean;
}

export interface MethodInfo {
  name: string;
  abstract?: boolean;
  property?: boolean;
  params?: string[];
  return_type?: string;
  docstring?: string;
}

export interface ModelEdge {
  id: string;
  source: string;
  target: string;
  relation: 'imports' | 'lazy_imports' | 'implements' | 'registered_in' | 'inherits' | 'uses';
  is_lazy?: boolean;
  metadata?: Record<string, unknown>;
}

export interface ModelGroup {
  id: string;
  name: string;
  color: string;
  description?: string;
  module_patterns?: string[];
}

export interface ModelInvariant {
  id: string;
  description: string;
  severity: 'must' | 'should' | 'info';
  source: 'code' | 'claude_md';
  file_path?: string;
  line_number?: number;
  related_nodes?: string[];
}

export interface ModelGraph {
  nodes: ModelNode[];
  edges: ModelEdge[];
  groups: ModelGroup[];
  invariants: ModelInvariant[];
  metadata: Record<string, unknown>;
  schema_version: string;
}

/** Layout node with position computed by d3-force. */
export interface LayoutNode extends ModelNode {
  x: number;
  y: number;
  vx?: number;
  vy?: number;
  fx?: number | null;
  fy?: number | null;
}
