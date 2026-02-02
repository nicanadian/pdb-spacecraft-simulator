/**
 * Sequence Panel - Activity hierarchy with branching support
 * Based on mockup: Sequence Editor - Proactive Branching Mode.png
 */

import { Component, For, Show, createSignal } from 'solid-js';
import { missionStore } from '@/stores/missionStore';
import { selectionStore } from '@/stores/selectionStore';
import type { Activity } from '@/types';

export const SequencePanel: Component = () => {
  const [selectedStepId, setSelectedStepId] = createSignal<string | null>(null);

  // Mock activities for demonstration
  const activities: Activity[] = [
    {
      id: 'propagate-1',
      type: 'propagate',
      name: 'Propagate',
      startTime: new Date(),
      endTime: new Date(Date.now() + 3600000),
      duration: 3600,
      parameters: {},
      status: 'completed',
      children: [
        {
          id: 'maneuver-1',
          type: 'maneuver',
          name: 'Maneuver',
          startTime: new Date(Date.now() + 1800000),
          endTime: new Date(Date.now() + 2400000),
          duration: 600,
          parameters: { deltaV: 2.5 },
          status: 'active',
          parentId: 'propagate-1',
          children: [
            {
              id: 'step-1',
              type: 'maneuver',
              name: 'Maneuver Step 1',
              startTime: new Date(Date.now() + 1800000),
              endTime: new Date(Date.now() + 2100000),
              duration: 300,
              parameters: { deltaV: 1.2 },
              status: 'pending',
              parentId: 'maneuver-1',
            },
          ],
        },
      ],
    },
  ];

  const isInBranchMode = () => missionStore.state.branchState === 'active';

  return (
    <div class="sequence-panel">
      {/* Panel Header */}
      <div class="panel-header">
        <h3>Steps</h3>
        <Show when={isInBranchMode()}>
          <div class="branch-mode-indicator">
            <span class="branch-mode-glow" />
            <span>Branching</span>
          </div>
        </Show>
      </div>

      {/* Steps Tree */}
      <div class="steps-tree">
        <For each={activities}>
          {(activity) => (
            <StepItem
              activity={activity}
              level={0}
              selectedId={selectedStepId()}
              onSelect={(id) => setSelectedStepId(id)}
            />
          )}
        </For>
      </div>

      {/* Step Editor (when step selected) */}
      <Show when={selectedStepId()}>
        <div class="step-editor">
          <StepEditor stepId={selectedStepId()!} />
        </div>
      </Show>

      {/* Triad Link Bar */}
      <div class="triad-link-bar">
        <div class="link-track">
          <div class="current-path solid-path" />
          <Show when={isInBranchMode()}>
            <div class="branch-path dashed-path" />
          </Show>
        </div>
      </div>

      <style>{`
        .sequence-panel {
          display: flex;
          flex-direction: column;
          height: 100%;
        }

        .panel-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: var(--space-4);
          border-bottom: 1px solid var(--neutral-border);
        }

        .panel-header h3 {
          font-size: var(--text-sm);
          font-weight: var(--font-semibold);
          color: var(--slate-700);
          margin: 0;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .branch-mode-indicator {
          display: flex;
          align-items: center;
          gap: var(--space-2);
          font-size: var(--text-xs);
          color: var(--electric-teal);
        }

        .steps-tree {
          flex: 1;
          overflow-y: auto;
          padding: var(--space-2);
        }

        .step-editor {
          border-top: 1px solid var(--neutral-border);
          padding: var(--space-4);
          background: var(--slate-50);
        }

        .triad-link-bar {
          padding: var(--space-3) var(--space-4);
          border-top: 1px solid var(--neutral-border);
          background: white;
        }

        .link-track {
          height: 8px;
          background: var(--slate-200);
          border-radius: var(--radius-full);
          position: relative;
          overflow: hidden;
        }

        .current-path {
          position: absolute;
          top: 3px;
          left: 10%;
          right: 50%;
          height: 2px;
          background: var(--electric-teal);
        }

        .branch-path {
          position: absolute;
          top: 3px;
          left: 50%;
          right: 10%;
          height: 2px;
          background: repeating-linear-gradient(
            to right,
            var(--electric-teal),
            var(--electric-teal) 6px,
            transparent 6px,
            transparent 10px
          );
        }
      `}</style>
    </div>
  );
};

// Step Item Component
interface StepItemProps {
  activity: Activity;
  level: number;
  selectedId: string | null;
  onSelect: (id: string) => void;
}

const StepItem: Component<StepItemProps> = (props) => {
  const [expanded, setExpanded] = createSignal(true);
  const hasChildren = () =>
    props.activity.children && props.activity.children.length > 0;
  const isSelected = () => props.selectedId === props.activity.id;

  const getStatusIcon = (status: Activity['status']): string => {
    switch (status) {
      case 'completed':
        return '\u2713';
      case 'active':
        return '\u25CF';
      case 'pending':
        return '\u25CB';
      default:
        return '\u25CB';
    }
  };

  return (
    <div class="step-item">
      <button
        class="step-row"
        classList={{ selected: isSelected() }}
        style={{ 'padding-left': `${props.level * 16 + 8}px` }}
        onClick={() => props.onSelect(props.activity.id)}
      >
        <Show when={hasChildren()}>
          <button
            class="expand-toggle"
            onClick={(e) => {
              e.stopPropagation();
              setExpanded(!expanded());
            }}
          >
            {expanded() ? '\u25BC' : '\u25B6'}
          </button>
        </Show>
        <Show when={!hasChildren()}>
          <span class="expand-placeholder" />
        </Show>

        <span
          class="status-icon"
          classList={{
            completed: props.activity.status === 'completed',
            active: props.activity.status === 'active',
            pending: props.activity.status === 'pending',
          }}
        >
          {getStatusIcon(props.activity.status)}
        </span>

        <span class="step-name">{props.activity.name}</span>
      </button>

      <Show when={hasChildren() && expanded()}>
        <div class="step-children">
          <For each={props.activity.children}>
            {(child) => (
              <StepItem
                activity={child}
                level={props.level + 1}
                selectedId={props.selectedId}
                onSelect={props.onSelect}
              />
            )}
          </For>
        </div>
      </Show>

      <style>{`
        .step-row {
          display: flex;
          align-items: center;
          gap: var(--space-2);
          width: 100%;
          padding: var(--space-2);
          border: none;
          background: transparent;
          cursor: pointer;
          border-radius: var(--radius-sm);
          font-size: var(--text-sm);
          text-align: left;
          color: var(--slate-700);
        }

        .step-row:hover {
          background: var(--slate-100);
        }

        .step-row.selected {
          background: rgba(8, 145, 178, 0.1);
          color: var(--electric-teal);
        }

        .expand-toggle {
          width: 16px;
          height: 16px;
          padding: 0;
          border: none;
          background: transparent;
          color: var(--slate-500);
          cursor: pointer;
          font-size: 8px;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .expand-placeholder {
          width: 16px;
        }

        .status-icon {
          font-size: 12px;
        }

        .status-icon.completed {
          color: var(--alert-success);
        }

        .status-icon.active {
          color: var(--electric-teal);
        }

        .status-icon.pending {
          color: var(--slate-400);
        }

        .step-name {
          flex: 1;
        }
      `}</style>
    </div>
  );
};

// Step Editor Component
interface StepEditorProps {
  stepId: string;
}

const StepEditor: Component<StepEditorProps> = (props) => {
  const [sections, setSections] = createSignal({
    parameters: true,
    description: false,
    variables: false,
  });

  const toggleSection = (section: keyof typeof sections) => {
    setSections((prev) => ({ ...prev, [section]: !prev[section] }));
  };

  return (
    <div class="step-editor-content">
      {/* Parameters Section */}
      <div class="editor-section">
        <button
          class="section-header"
          onClick={() => toggleSection('parameters')}
        >
          <span class="section-toggle">
            {sections().parameters ? '\u25BC' : '\u25B6'}
          </span>
          <span class="section-title">Parameters</span>
        </button>
        <Show when={sections().parameters}>
          <div class="section-content">
            <div class="param-row">
              <span class="param-label">Delta-V</span>
              <span class="param-value font-mono">2.5 m/s</span>
            </div>
            <div class="param-row">
              <span class="param-label">Duration</span>
              <span class="param-value font-mono">600 s</span>
            </div>
            <div class="param-row">
              <span class="param-label">Thrust Direction</span>
              <span class="param-value font-mono">Velocity</span>
            </div>
          </div>
        </Show>
      </div>

      {/* Description Section */}
      <div class="editor-section">
        <button
          class="section-header"
          onClick={() => toggleSection('description')}
        >
          <span class="section-toggle">
            {sections().description ? '\u25BC' : '\u25B6'}
          </span>
          <span class="section-title">Description</span>
        </button>
        <Show when={sections().description}>
          <div class="section-content">
            <p class="description-text">
              Orbital maintenance maneuver to maintain altitude.
            </p>
          </div>
        </Show>
      </div>

      <style>{`
        .step-editor-content {
          display: flex;
          flex-direction: column;
          gap: var(--space-2);
        }

        .editor-section {
          border: 1px solid var(--neutral-border);
          border-radius: var(--radius-md);
          overflow: hidden;
        }

        .section-header {
          display: flex;
          align-items: center;
          gap: var(--space-2);
          width: 100%;
          padding: var(--space-2) var(--space-3);
          border: none;
          background: white;
          cursor: pointer;
          font-size: var(--text-sm);
        }

        .section-header:hover {
          background: var(--slate-50);
        }

        .section-toggle {
          font-size: 8px;
          color: var(--slate-500);
        }

        .section-title {
          font-weight: var(--font-medium);
          color: var(--slate-700);
        }

        .section-content {
          padding: var(--space-3);
          background: white;
          border-top: 1px solid var(--neutral-border);
        }

        .param-row {
          display: flex;
          justify-content: space-between;
          padding: var(--space-1) 0;
        }

        .param-label {
          font-size: var(--text-xs);
          color: var(--slate-500);
        }

        .param-value {
          font-size: var(--text-sm);
          color: var(--slate-800);
        }

        .description-text {
          font-size: var(--text-sm);
          color: var(--slate-600);
          margin: 0;
        }
      `}</style>
    </div>
  );
};
