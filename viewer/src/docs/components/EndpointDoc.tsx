/**
 * EndpointDoc - REST/GraphQL endpoint documentation
 */

import { Component, For, Show } from 'solid-js';
import { CodeBlock } from './CodeBlock';
import type { DocEndpoint } from '../types';

interface EndpointDocProps {
  endpoint: DocEndpoint;
}

const methodColors: Record<string, string> = {
  GET: '#10B981',
  POST: '#3B82F6',
  PUT: '#F59E0B',
  DELETE: '#DC2626',
  QUERY: '#8B5CF6',
  MUTATION: '#EC4899',
};

export const EndpointDoc: Component<EndpointDocProps> = (props) => {
  const methodColor = () => methodColors[props.endpoint.method] || '#6B7280';

  return (
    <div class="endpoint-doc" id={props.endpoint.path.replace(/[^a-zA-Z0-9]/g, '-')}>
      <div class="endpoint-header">
        <span
          class="endpoint-method"
          style={{ background: methodColor() }}
        >
          {props.endpoint.method}
        </span>
        <code class="endpoint-path">{props.endpoint.path}</code>
      </div>

      <p class="endpoint-description">{props.endpoint.description}</p>

      <Show when={props.endpoint.auth}>
        <div class="endpoint-auth">
          <span class="auth-label">🔐 Auth:</span>
          <span class="auth-value">{props.endpoint.auth}</span>
        </div>
      </Show>

      <Show when={props.endpoint.parameters && props.endpoint.parameters.length > 0}>
        <div class="endpoint-section">
          <h4 class="section-title">Parameters</h4>
          <table class="params-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Type</th>
                <th>Required</th>
                <th>Default</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              <For each={props.endpoint.parameters}>
                {(param) => (
                  <tr>
                    <td><code>{param.name}</code></td>
                    <td><code class="type">{param.type}</code></td>
                    <td>{param.required ? '✓' : '—'}</td>
                    <td>{param.default ? <code>{param.default}</code> : '—'}</td>
                    <td>{param.description}</td>
                  </tr>
                )}
              </For>
            </tbody>
          </table>
        </div>
      </Show>

      <Show when={props.endpoint.requestBody}>
        <div class="endpoint-section">
          <h4 class="section-title">Request Body</h4>
          <p class="content-type">Content-Type: <code>{props.endpoint.requestBody!.contentType}</code></p>
          <Show when={props.endpoint.requestBody!.example}>
            <CodeBlock
              code={props.endpoint.requestBody!.example!}
              language="json"
              title="Request"
            />
          </Show>
        </div>
      </Show>

      <Show when={props.endpoint.response}>
        <div class="endpoint-section">
          <h4 class="section-title">Response</h4>
          <p class="response-status">
            Status: <code>{props.endpoint.response!.status}</code> — {props.endpoint.response!.description}
          </p>
          <Show when={props.endpoint.response!.example}>
            <CodeBlock
              code={props.endpoint.response!.example!}
              language="json"
              title="Response"
            />
          </Show>
        </div>
      </Show>

      <Show when={props.endpoint.example}>
        <div class="endpoint-section">
          <h4 class="section-title">Example</h4>
          <Show when={props.endpoint.example!.description}>
            <p class="example-desc">{props.endpoint.example!.description}</p>
          </Show>
          <Show when={props.endpoint.example!.request}>
            <CodeBlock
              code={props.endpoint.example!.request!}
              language="bash"
              title="Request"
            />
          </Show>
          <Show when={props.endpoint.example!.response}>
            <CodeBlock
              code={props.endpoint.example!.response!}
              language="json"
              title="Response"
            />
          </Show>
        </div>
      </Show>

      <style>{`
        .endpoint-doc {
          padding: var(--space-5);
          background: var(--slate-800);
          border-radius: var(--radius-md);
          border: 1px solid var(--slate-700);
          margin-bottom: var(--space-4);
        }

        .endpoint-header {
          display: flex;
          align-items: center;
          gap: var(--space-3);
          margin-bottom: var(--space-3);
        }

        .endpoint-method {
          padding: var(--space-1) var(--space-2);
          border-radius: var(--radius-sm);
          font-size: var(--text-xs);
          font-weight: var(--font-bold);
          font-family: var(--font-mono);
          color: white;
          text-transform: uppercase;
        }

        .endpoint-path {
          font-family: var(--font-mono);
          font-size: var(--text-base);
          color: var(--ghost-slate);
        }

        .endpoint-description {
          color: var(--slate-300);
          font-size: var(--text-sm);
          line-height: 1.6;
          margin-bottom: var(--space-4);
        }

        .endpoint-auth {
          display: flex;
          align-items: center;
          gap: var(--space-2);
          padding: var(--space-2) var(--space-3);
          background: var(--slate-700);
          border-radius: var(--radius-sm);
          margin-bottom: var(--space-4);
          font-size: var(--text-sm);
        }

        .auth-label {
          color: var(--slate-400);
        }

        .auth-value {
          color: var(--ghost-slate);
          font-family: var(--font-mono);
        }

        .endpoint-section {
          margin-top: var(--space-4);
          padding-top: var(--space-4);
          border-top: 1px solid var(--slate-700);
        }

        .section-title {
          font-size: var(--text-sm);
          font-weight: var(--font-semibold);
          color: var(--ghost-slate);
          margin: 0 0 var(--space-3) 0;
        }

        .params-table {
          width: 100%;
          border-collapse: collapse;
          font-size: var(--text-sm);
        }

        .params-table th,
        .params-table td {
          padding: var(--space-2) var(--space-3);
          text-align: left;
          border-bottom: 1px solid var(--slate-700);
        }

        .params-table th {
          color: var(--slate-400);
          font-weight: var(--font-medium);
          background: var(--slate-750);
        }

        .params-table td {
          color: var(--slate-300);
        }

        .params-table code {
          background: var(--slate-700);
          padding: 2px 6px;
          border-radius: var(--radius-sm);
          font-size: var(--text-xs);
        }

        .params-table code.type {
          color: var(--electric-teal);
        }

        .content-type,
        .response-status {
          font-size: var(--text-sm);
          color: var(--slate-400);
          margin-bottom: var(--space-3);
        }

        .content-type code,
        .response-status code {
          background: var(--slate-700);
          padding: 2px 6px;
          border-radius: var(--radius-sm);
          color: var(--ghost-slate);
        }

        .example-desc {
          font-size: var(--text-sm);
          color: var(--slate-400);
          margin-bottom: var(--space-3);
        }
      `}</style>
    </div>
  );
};
