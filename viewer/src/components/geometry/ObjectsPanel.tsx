/**
 * Objects Panel - Collapsible tree of scene objects
 * Based on mockup: The High-Fidelity Workspace.png
 */

import { Component, For, createSignal, Show } from 'solid-js';
import { cesiumService } from '@/services/cesiumService';
import { selectionStore } from '@/stores/selectionStore';

interface ObjectsPanelProps {
  onClose: () => void;
}

interface TreeNode {
  id: string;
  name: string;
  type: 'folder' | 'satellite' | 'station' | 'view';
  children?: TreeNode[];
  expanded?: boolean;
}

export const ObjectsPanel: Component<ObjectsPanelProps> = (props) => {
  // Build tree from Cesium entities
  const [tree, setTree] = createSignal<TreeNode[]>([
    {
      id: 'satellites',
      name: 'Satellites',
      type: 'folder',
      expanded: true,
      children: [
        { id: 'spacecraft', name: 'Spacecraft', type: 'satellite' },
      ],
    },
    {
      id: 'stations',
      name: 'Ground Stations',
      type: 'folder',
      expanded: false,
      children: [],
    },
    {
      id: 'views',
      name: 'Views',
      type: 'folder',
      expanded: false,
      children: [
        { id: 'view-earth', name: 'Earth Overview', type: 'view' },
        { id: 'view-orbit', name: 'Orbit View', type: 'view' },
      ],
    },
  ]);

  const toggleExpand = (nodeId: string) => {
    setTree((prev) =>
      prev.map((node) =>
        node.id === nodeId
          ? { ...node, expanded: !node.expanded }
          : {
              ...node,
              children: node.children?.map((child) =>
                child.id === nodeId
                  ? { ...child, expanded: !child.expanded }
                  : child
              ),
            }
      )
    );
  };

  const handleSelect = (node: TreeNode) => {
    if (node.type === 'satellite' || node.type === 'station') {
      selectionStore.selectEntity(node.id);
      cesiumService.focusOnEntity(node.id);
    } else if (node.type === 'view') {
      // Handle view selection
      if (node.id === 'view-earth') {
        cesiumService.resetView();
      }
    }
  };

  const getIcon = (type: TreeNode['type']): string => {
    switch (type) {
      case 'folder':
        return '\u{1F4C1}';
      case 'satellite':
        return '\u{1F6F0}';
      case 'station':
        return '\u{1F4E1}';
      case 'view':
        return '\u{1F441}';
      default:
        return '\u25CF';
    }
  };

  return (
    <div class="objects-panel">
      <div class="panel-header">
        <span class="header-title">Objects</span>
        <button class="close-btn" onClick={props.onClose}>
          {'\u2715'}
        </button>
      </div>

      <div class="panel-content">
        <For each={tree()}>
          {(node) => (
            <TreeItem
              node={node}
              level={0}
              onToggle={toggleExpand}
              onSelect={handleSelect}
              getIcon={getIcon}
            />
          )}
        </For>
      </div>

      <style>{`
        .objects-panel {
          display: flex;
          flex-direction: column;
          height: 100%;
        }

        .panel-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: var(--space-3) var(--space-4);
          border-bottom: 1px solid var(--neutral-border);
        }

        .header-title {
          font-size: var(--text-sm);
          font-weight: var(--font-semibold);
          color: var(--slate-700);
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .close-btn {
          width: 24px;
          height: 24px;
          border: none;
          background: transparent;
          color: var(--slate-500);
          cursor: pointer;
          border-radius: var(--radius-sm);
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .close-btn:hover {
          background: var(--slate-100);
          color: var(--slate-700);
        }

        .panel-content {
          flex: 1;
          overflow-y: auto;
          padding: var(--space-2);
        }
      `}</style>
    </div>
  );
};

// Tree Item Component
interface TreeItemProps {
  node: TreeNode;
  level: number;
  onToggle: (id: string) => void;
  onSelect: (node: TreeNode) => void;
  getIcon: (type: TreeNode['type']) => string;
}

const TreeItem: Component<TreeItemProps> = (props) => {
  const hasChildren = () =>
    props.node.children && props.node.children.length > 0;
  const isSelected = () =>
    selectionStore.selectedEntity() === props.node.id;

  return (
    <div class="tree-item">
      <button
        class="tree-item-row"
        classList={{
          selected: isSelected(),
          folder: props.node.type === 'folder',
        }}
        style={{ 'padding-left': `${props.level * 16 + 8}px` }}
        onClick={() => {
          if (hasChildren()) {
            props.onToggle(props.node.id);
          } else {
            props.onSelect(props.node);
          }
        }}
      >
        <Show when={hasChildren()}>
          <span class="expand-icon">
            {props.node.expanded ? '\u25BC' : '\u25B6'}
          </span>
        </Show>
        <Show when={!hasChildren()}>
          <span class="expand-placeholder" />
        </Show>
        <span class="item-icon">{props.getIcon(props.node.type)}</span>
        <span class="item-name">{props.node.name}</span>
      </button>

      <Show when={hasChildren() && props.node.expanded}>
        <div class="tree-children">
          <For each={props.node.children}>
            {(child) => (
              <TreeItem
                node={child}
                level={props.level + 1}
                onToggle={props.onToggle}
                onSelect={props.onSelect}
                getIcon={props.getIcon}
              />
            )}
          </For>
        </div>
      </Show>

      <style>{`
        .tree-item-row {
          display: flex;
          align-items: center;
          gap: var(--space-2);
          width: 100%;
          padding: var(--space-2) var(--space-2);
          border: none;
          background: transparent;
          cursor: pointer;
          border-radius: var(--radius-sm);
          font-size: var(--text-sm);
          text-align: left;
          color: var(--slate-700);
        }

        .tree-item-row:hover {
          background: var(--slate-100);
        }

        .tree-item-row.selected {
          background: rgba(8, 145, 178, 0.1);
          color: var(--electric-teal);
        }

        .tree-item-row.folder {
          font-weight: var(--font-medium);
        }

        .expand-icon {
          font-size: 8px;
          width: 12px;
          color: var(--slate-500);
        }

        .expand-placeholder {
          width: 12px;
        }

        .item-icon {
          font-size: 14px;
        }

        .item-name {
          flex: 1;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .tree-children {
          margin-left: 0;
        }
      `}</style>
    </div>
  );
};
