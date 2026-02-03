/**
 * CodeBlock - Syntax-highlighted code with copy-to-clipboard
 */

import { Component, createSignal, Show } from 'solid-js';

interface CodeBlockProps {
  code: string;
  language?: string;
  title?: string;
}

export const CodeBlock: Component<CodeBlockProps> = (props) => {
  const [copied, setCopied] = createSignal(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(props.code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  return (
    <div class="code-block">
      <Show when={props.title || props.language}>
        <div class="code-header">
          <span class="code-title">{props.title || props.language}</span>
          <button
            class="copy-btn"
            onClick={handleCopy}
            title="Copy to clipboard"
          >
            {copied() ? '✓ Copied' : 'Copy'}
          </button>
        </div>
      </Show>
      <Show when={!props.title && !props.language}>
        <button
          class="copy-btn floating"
          onClick={handleCopy}
          title="Copy to clipboard"
        >
          {copied() ? '✓' : '⎘'}
        </button>
      </Show>
      <pre class="code-content">
        <code class={`language-${props.language || 'text'}`}>
          {props.code}
        </code>
      </pre>

      <style>{`
        .code-block {
          position: relative;
          background: var(--slate-900);
          border-radius: var(--radius-md);
          overflow: hidden;
          margin: var(--space-4) 0;
          border: 1px solid var(--slate-700);
        }

        .code-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: var(--space-2) var(--space-4);
          background: var(--slate-800);
          border-bottom: 1px solid var(--slate-700);
        }

        .code-title {
          font-size: var(--text-xs);
          font-family: var(--font-mono);
          color: var(--slate-400);
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }

        .copy-btn {
          padding: var(--space-1) var(--space-2);
          font-size: var(--text-xs);
          font-family: var(--font-mono);
          background: transparent;
          border: 1px solid var(--slate-600);
          border-radius: var(--radius-sm);
          color: var(--slate-400);
          cursor: pointer;
          transition: all var(--transition-fast);
        }

        .copy-btn:hover {
          background: var(--slate-700);
          color: var(--ghost-slate);
          border-color: var(--slate-500);
        }

        .copy-btn.floating {
          position: absolute;
          top: var(--space-2);
          right: var(--space-2);
          opacity: 0;
          z-index: 1;
        }

        .code-block:hover .copy-btn.floating {
          opacity: 1;
        }

        .code-content {
          margin: 0;
          padding: var(--space-4);
          overflow-x: auto;
          font-family: var(--font-mono);
          font-size: var(--text-sm);
          line-height: 1.6;
          color: var(--slate-200);
        }

        .code-content code {
          font-family: inherit;
        }

        /* Basic syntax highlighting */
        .code-content .keyword { color: #c792ea; }
        .code-content .string { color: #c3e88d; }
        .code-content .number { color: #f78c6c; }
        .code-content .comment { color: #546e7a; }
        .code-content .function { color: #82aaff; }
      `}</style>
    </div>
  );
};
