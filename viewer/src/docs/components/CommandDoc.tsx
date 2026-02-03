/**
 * CommandDoc - CLI command documentation
 */

import { Component, For, Show } from 'solid-js';
import { CodeBlock } from './CodeBlock';
import type { DocCommand } from '../types';

interface CommandDocProps {
  command: DocCommand;
  depth?: number;
}

export const CommandDoc: Component<CommandDocProps> = (props) => {
  const depth = props.depth ?? 0;

  return (
    <div
      class="command-doc"
      id={props.command.name.replace(/\s+/g, '-')}
      classList={{ nested: depth > 0 }}
    >
      <div class="command-header">
        <code class="command-name">{props.command.name}</code>
        <span class="command-description">{props.command.description}</span>
      </div>

      <div class="command-usage">
        <h4 class="usage-title">Usage</h4>
        <CodeBlock code={props.command.usage} language="bash" />
      </div>

      <Show when={props.command.flags && props.command.flags.length > 0}>
        <div class="command-section">
          <h4 class="section-title">Options</h4>
          <table class="flags-table">
            <thead>
              <tr>
                <th>Flag</th>
                <th>Type</th>
                <th>Default</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              <For each={props.command.flags}>
                {(flag) => (
                  <tr>
                    <td>
                      <code class="flag-name">
                        {flag.short ? `-${flag.short}, ` : ''}--{flag.name}
                      </code>
                      <Show when={flag.required}>
                        <span class="required-badge">required</span>
                      </Show>
                    </td>
                    <td><code class="type">{flag.type}</code></td>
                    <td>{flag.default ? <code>{flag.default}</code> : '—'}</td>
                    <td>{flag.description}</td>
                  </tr>
                )}
              </For>
            </tbody>
          </table>
        </div>
      </Show>

      <Show when={props.command.examples && props.command.examples.length > 0}>
        <div class="command-section">
          <h4 class="section-title">Examples</h4>
          <For each={props.command.examples}>
            {(example) => (
              <CodeBlock code={example} language="bash" />
            )}
          </For>
        </div>
      </Show>

      <Show when={props.command.subcommands && props.command.subcommands.length > 0}>
        <div class="command-section">
          <h4 class="section-title">Subcommands</h4>
          <div class="subcommands">
            <For each={props.command.subcommands}>
              {(sub) => <CommandDoc command={sub} depth={depth + 1} />}
            </For>
          </div>
        </div>
      </Show>

      <style>{`
        .command-doc {
          padding: var(--space-5);
          background: var(--slate-800);
          border-radius: var(--radius-md);
          border: 1px solid var(--slate-700);
          margin-bottom: var(--space-4);
        }

        .command-doc.nested {
          background: var(--slate-750);
          border-color: var(--slate-600);
          margin-left: var(--space-4);
        }

        .command-header {
          display: flex;
          flex-direction: column;
          gap: var(--space-2);
          margin-bottom: var(--space-4);
        }

        .command-name {
          font-family: var(--font-mono);
          font-size: var(--text-lg);
          color: var(--electric-teal);
          background: var(--slate-900);
          padding: var(--space-2) var(--space-3);
          border-radius: var(--radius-sm);
          display: inline-block;
        }

        .command-description {
          color: var(--slate-300);
          font-size: var(--text-sm);
          line-height: 1.6;
        }

        .command-usage {
          margin-bottom: var(--space-4);
        }

        .usage-title,
        .section-title {
          font-size: var(--text-sm);
          font-weight: var(--font-semibold);
          color: var(--ghost-slate);
          margin: 0 0 var(--space-3) 0;
        }

        .command-section {
          margin-top: var(--space-4);
          padding-top: var(--space-4);
          border-top: 1px solid var(--slate-700);
        }

        .flags-table {
          width: 100%;
          border-collapse: collapse;
          font-size: var(--text-sm);
        }

        .flags-table th,
        .flags-table td {
          padding: var(--space-2) var(--space-3);
          text-align: left;
          border-bottom: 1px solid var(--slate-700);
        }

        .flags-table th {
          color: var(--slate-400);
          font-weight: var(--font-medium);
          background: var(--slate-750);
        }

        .flags-table td {
          color: var(--slate-300);
        }

        .flag-name {
          background: var(--slate-700);
          padding: 2px 6px;
          border-radius: var(--radius-sm);
          font-size: var(--text-xs);
          color: var(--ghost-slate);
        }

        .required-badge {
          display: inline-block;
          margin-left: var(--space-2);
          padding: 1px 6px;
          background: var(--color-alert-warning-bg);
          color: var(--color-alert-warning);
          font-size: var(--text-xs);
          border-radius: var(--radius-sm);
        }

        .flags-table code.type {
          color: var(--electric-teal);
          background: var(--slate-700);
          padding: 2px 6px;
          border-radius: var(--radius-sm);
        }

        .subcommands {
          display: flex;
          flex-direction: column;
          gap: var(--space-3);
        }
      `}</style>
    </div>
  );
};
