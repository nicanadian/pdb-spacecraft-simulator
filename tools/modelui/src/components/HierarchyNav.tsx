import { For, Show } from 'solid-js';
import {
  hierarchyTree, expandedNodes, toggleExpanded, setFocusNodeId, focusNodeId,
} from '../stores/modelStore';
import type { HierarchyTreeNode } from '../stores/modelStore';

const LEVEL_INDENT: Record<string, number> = {
  L0: 0, L1: 12, L2: 24, L3: 36,
};

const LEVEL_COLORS: Record<string, string> = {
  L0: '#f59e0b',
  L1: '#ef4444',
  L2: '#06b6d4',
  L3: '#22c55e',
};

function TreeNode(props: { node: HierarchyTreeNode; depth: number }) {
  const isExpanded = () => expandedNodes().has(props.node.id);
  const isFocused = () => focusNodeId() === props.node.id;
  const hasChildren = () => props.node.children.length > 0;
  const indent = () => props.depth * 14;

  return (
    <>
      <button
        onClick={() => setFocusNodeId(isFocused() ? null : props.node.id)}
        style={{
          display: 'flex',
          'align-items': 'center',
          gap: '6px',
          width: '100%',
          padding: `4px 8px 4px ${indent() + 8}px`,
          background: isFocused() ? '#334155' : 'transparent',
          border: 'none',
          'border-radius': '4px',
          color: isFocused() ? '#f1f5f9' : '#cbd5e1',
          'font-size': '12px',
          cursor: 'pointer',
          'text-align': 'left',
        }}
      >
        {/* Expand toggle */}
        <Show when={hasChildren()}>
          <span
            onClick={(e) => { e.stopPropagation(); toggleExpanded(props.node.id); }}
            style={{
              width: '14px',
              height: '14px',
              display: 'flex',
              'align-items': 'center',
              'justify-content': 'center',
              'font-size': '10px',
              color: '#64748b',
              'flex-shrink': '0',
            }}
          >
            {isExpanded() ? '\u25BC' : '\u25B6'}
          </span>
        </Show>
        <Show when={!hasChildren()}>
          <span style={{ width: '14px', 'flex-shrink': '0' }} />
        </Show>

        {/* Level badge */}
        <span style={{
          'font-size': '9px',
          'font-weight': '600',
          color: LEVEL_COLORS[props.node.level] ?? '#64748b',
          'flex-shrink': '0',
        }}>
          {props.node.level}
        </span>

        {/* Name */}
        <span style={{ overflow: 'hidden', 'text-overflow': 'ellipsis', 'white-space': 'nowrap' }}>
          {props.node.name}
        </span>

        {/* Child count */}
        <Show when={hasChildren()}>
          <span style={{ 'font-size': '10px', color: '#475569', 'margin-left': 'auto', 'flex-shrink': '0' }}>
            {props.node.children.length}
          </span>
        </Show>
      </button>

      {/* Children */}
      <Show when={isExpanded()}>
        <For each={props.node.children}>
          {(child) => <TreeNode node={child} depth={props.depth + 1} />}
        </For>
      </Show>
    </>
  );
}

export default function HierarchyNav() {
  const tree = hierarchyTree;

  return (
    <div style={{ padding: '0 8px' }}>
      <div style={{
        'font-size': '11px',
        color: '#94a3b8',
        'margin-bottom': '8px',
        'text-transform': 'uppercase',
        'letter-spacing': '0.05em',
        padding: '0 8px',
      }}>
        Hierarchy
      </div>
      <div style={{ 'max-height': '400px', overflow: 'auto' }}>
        <For each={tree()}>
          {(node) => <TreeNode node={node} depth={0} />}
        </For>
      </div>
    </div>
  );
}
