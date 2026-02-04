import { createMemo, For, Show } from 'solid-js';
import {
  requirementItems, requirementLinks, archNodes,
  selectedNodeId, setSelectedNodeId,
} from '../stores/modelStore';
import type { Requirement } from '../types/model';

const REQ_TYPE_COLORS: Record<string, { bg: string; fg: string }> = {
  Need: { bg: '#dc2626', fg: '#fef2f2' },
  CapabilityRequirement: { bg: '#f59e0b', fg: '#451a03' },
  ArchitectureConstraint: { bg: '#06b6d4', fg: '#083344' },
  InterfaceContract: { bg: '#22c55e', fg: '#052e16' },
  QualityAttribute: { bg: '#8b5cf6', fg: '#faf5ff' },
  VerificationRequirement: { bg: '#64748b', fg: '#f1f5f9' },
};

export default function RequirementsView() {
  const reqs = requirementItems;
  const links = requirementLinks;
  const allNodes = archNodes;

  // Build tree: requirements with no parent at root
  const rootReqs = createMemo(() =>
    reqs().filter(r => !r.parent_id)
  );

  const childReqsOf = (parentId: string) =>
    reqs().filter(r => r.parent_id === parentId);

  const allocationsFor = (reqId: string) => {
    const allocs = links().filter(lk => lk.requirement_id === reqId && lk.relation === 'allocatedTo');
    return allocs.map(lk => {
      const node = allNodes().find(n => n.id === lk.target_id);
      return { id: lk.target_id, name: node?.name ?? lk.target_id };
    });
  };

  return (
    <div style={{ padding: '24px', overflow: 'auto', height: '100%' }}>
      <h2 style={{ 'font-size': '18px', 'font-weight': '600', color: '#f1f5f9', margin: '0 0 20px 0' }}>
        Requirements Decomposition
      </h2>
      <div style={{ display: 'flex', 'flex-direction': 'column', gap: '12px' }}>
        <For each={rootReqs()}>
          {(req) => <ReqNode req={req} depth={0} childReqsOf={childReqsOf} allocationsFor={allocationsFor} />}
        </For>
      </div>
    </div>
  );
}

function ReqNode(props: {
  req: Requirement;
  depth: number;
  childReqsOf: (id: string) => Requirement[];
  allocationsFor: (id: string) => { id: string; name: string }[];
}) {
  const colors = () => REQ_TYPE_COLORS[props.req.req_type] ?? REQ_TYPE_COLORS.VerificationRequirement;
  const children = () => props.childReqsOf(props.req.id);
  const allocs = () => props.allocationsFor(props.req.id);
  const selected = () => selectedNodeId() === props.req.id;

  return (
    <div style={{ 'margin-left': `${props.depth * 24}px` }}>
      <div
        onClick={() => setSelectedNodeId(selected() ? null : props.req.id)}
        style={{
          background: selected() ? '#334155' : '#1e293b',
          'border-radius': '8px',
          padding: '12px 16px',
          border: `1px solid ${selected() ? '#475569' : '#334155'}`,
          cursor: 'pointer',
          'margin-bottom': '8px',
        }}
      >
        <div style={{ display: 'flex', 'align-items': 'center', gap: '10px', 'margin-bottom': '6px' }}>
          {/* Type badge */}
          <span style={{
            padding: '2px 8px',
            'border-radius': '4px',
            'font-size': '10px',
            'font-weight': '600',
            background: colors().bg,
            color: colors().fg,
            'text-transform': 'uppercase',
          }}>
            {props.req.req_type}
          </span>
          <span style={{ 'font-size': '12px', color: '#64748b', 'font-family': 'monospace' }}>
            {props.req.id}
          </span>
          <Show when={props.req.level}>
            <span style={{ 'font-size': '10px', color: '#475569' }}>
              {props.req.level}
            </span>
          </Show>
        </div>
        <div style={{ 'font-size': '14px', color: '#e2e8f0', 'font-weight': '500' }}>
          {props.req.title}
        </div>
        <Show when={props.req.description}>
          <div style={{ 'font-size': '12px', color: '#94a3b8', 'margin-top': '4px' }}>
            {props.req.description}
          </div>
        </Show>
        {/* Allocations */}
        <Show when={allocs().length > 0}>
          <div style={{ display: 'flex', gap: '6px', 'margin-top': '8px', 'flex-wrap': 'wrap' }}>
            <For each={allocs()}>
              {(alloc) => (
                <span style={{
                  padding: '2px 8px',
                  'border-radius': '4px',
                  'font-size': '10px',
                  background: '#0f172a',
                  color: '#7dd3fc',
                  border: '1px solid #1e3a5f',
                  'font-family': 'monospace',
                }}>
                  {alloc.name}
                </span>
              )}
            </For>
          </div>
        </Show>
      </div>
      {/* Children */}
      <For each={children()}>
        {(child) => (
          <ReqNode
            req={child}
            depth={props.depth + 1}
            childReqsOf={props.childReqsOf}
            allocationsFor={props.allocationsFor}
          />
        )}
      </For>
    </div>
  );
}
