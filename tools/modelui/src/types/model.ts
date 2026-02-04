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

// ---------------------------------------------------------------------------
// UAF-lite v2 architecture types
// ---------------------------------------------------------------------------

export type ArchLevel = 'L0' | 'L1' | 'L2' | 'L3' | 'L4';

export type ViewId =
  | 'operational-context'
  | 'capability-map'
  | 'logical-architecture'
  | 'interface-contracts'
  | 'technical-deployment'
  | 'requirements-decomposition';

export interface ArchNode {
  id: string;
  name: string;
  level: ArchLevel;
  arch_type: string;
  parent_id: string;
  domain: string;
  description: string;
  ir_node_ref: string;
  children: string[];
  tags: string[];
  metadata: Record<string, unknown>;
}

export interface ArchEdge {
  id: string;
  source: string;
  target: string;
  relation: string;
  metadata: Record<string, unknown>;
}

export interface Requirement {
  id: string;
  title: string;
  req_type: string;
  level: string;
  description: string;
  parent_id: string;
  children: string[];
  source: string;
  metadata: Record<string, unknown>;
}

export interface RequirementLink {
  id: string;
  requirement_id: string;
  target_id: string;
  relation: string;
}

export interface ViewpointDef {
  id: ViewId;
  name: string;
  include_layers: ArchLevel[];
  domain: string;
  connector_types: string[];
  default_collapse: string[];
  overlays: string[];
}

export interface ArchModelGraph {
  schema_version: string;
  meta_model_version: string;
  metadata: Record<string, unknown>;
  architecture: {
    nodes: ArchNode[];
    edges: ArchEdge[];
  };
  requirements: {
    items: Requirement[];
    links: RequirementLink[];
  };
  viewpoints: ViewpointDef[];
  ir_graph: ModelGraph;
}

export interface TreeLayoutNode {
  id: string;
  label: string;
  level: ArchLevel;
  x: number;
  y: number;
  width: number;
  height: number;
  children: TreeLayoutNode[];
  collapsed: boolean;
  color: string;
  parentId: string | null;
  archNode?: ArchNode;
}
