/**
 * DocNav - Left navigation for documentation
 */

import { Component, For, Show, createSignal } from 'solid-js';
import type { DocSection } from '../types';

interface DocNavProps {
  sections: DocSection[];
  activeSection: string;
  onNavigate: (sectionId: string) => void;
}

export const DocNav: Component<DocNavProps> = (props) => {
  const [expandedSections, setExpandedSections] = createSignal<Set<string>>(new Set(['overview', 'interfaces', 'user-manual']));

  const toggleSection = (sectionId: string) => {
    const expanded = new Set(expandedSections());
    if (expanded.has(sectionId)) {
      expanded.delete(sectionId);
    } else {
      expanded.add(sectionId);
    }
    setExpandedSections(expanded);
  };

  const isActive = (sectionId: string) => props.activeSection === sectionId;
  const isExpanded = (sectionId: string) => expandedSections().has(sectionId);

  const renderSection = (section: DocSection, depth: number = 0) => {
    const hasChildren = section.children && section.children.length > 0;

    return (
      <div class="nav-section" style={{ '--depth': depth }}>
        <button
          class="nav-item"
          classList={{
            active: isActive(section.id),
            'has-children': hasChildren,
            expanded: hasChildren && isExpanded(section.id),
          }}
          onClick={() => {
            if (hasChildren) {
              toggleSection(section.id);
            }
            props.onNavigate(section.id);
          }}
        >
          <Show when={section.icon}>
            <span class="nav-icon">{section.icon}</span>
          </Show>
          <span class="nav-label">{section.title}</span>
          <Show when={hasChildren}>
            <span class="nav-chevron">{isExpanded(section.id) ? '▾' : '▸'}</span>
          </Show>
        </button>

        <Show when={hasChildren && isExpanded(section.id)}>
          <div class="nav-children">
            <For each={section.children}>
              {(child) => renderSection(child, depth + 1)}
            </For>
          </div>
        </Show>
      </div>
    );
  };

  return (
    <nav class="doc-nav">
      <For each={props.sections}>
        {(section) => renderSection(section)}
      </For>

      <style>{`
        .doc-nav {
          display: flex;
          flex-direction: column;
          padding: var(--space-3);
          gap: var(--space-1);
        }

        .nav-section {
          display: flex;
          flex-direction: column;
        }

        .nav-item {
          display: flex;
          align-items: center;
          gap: var(--space-2);
          padding: var(--space-2) var(--space-3);
          padding-left: calc(var(--space-3) + (var(--depth) * var(--space-4)));
          background: transparent;
          border: none;
          border-radius: var(--radius-sm);
          color: var(--slate-400);
          font-size: var(--text-sm);
          text-align: left;
          cursor: pointer;
          transition: all var(--transition-fast);
          width: 100%;
        }

        .nav-item:hover {
          background: var(--slate-800);
          color: var(--ghost-slate);
        }

        .nav-item.active {
          background: var(--slate-800);
          color: var(--electric-teal);
        }

        .nav-item.active::before {
          content: '';
          position: absolute;
          left: 0;
          width: 3px;
          height: 20px;
          background: var(--electric-teal);
          border-radius: 0 2px 2px 0;
        }

        .nav-icon {
          font-size: 14px;
          width: 18px;
          text-align: center;
          flex-shrink: 0;
        }

        .nav-label {
          flex: 1;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .nav-chevron {
          font-size: 10px;
          color: var(--slate-500);
          margin-left: auto;
        }

        .nav-children {
          display: flex;
          flex-direction: column;
          gap: var(--space-1);
          margin-top: var(--space-1);
        }
      `}</style>
    </nav>
  );
};
