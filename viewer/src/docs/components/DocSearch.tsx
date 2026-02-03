/**
 * DocSearch - Search across documentation content
 */

import { Component, createSignal, For, Show } from 'solid-js';
import type { DocSearchResult } from '../types';

interface DocSearchProps {
  searchIndex: DocSearchResult[];
  onNavigate: (sectionId: string, anchor?: string) => void;
}

export const DocSearch: Component<DocSearchProps> = (props) => {
  const [query, setQuery] = createSignal('');
  const [focused, setFocused] = createSignal(false);

  const results = () => {
    const q = query().toLowerCase().trim();
    if (q.length < 2) return [];

    return props.searchIndex
      .filter(item =>
        item.title.toLowerCase().includes(q) ||
        item.content.toLowerCase().includes(q)
      )
      .slice(0, 10);
  };

  const handleSelect = (result: DocSearchResult) => {
    props.onNavigate(result.sectionId, result.anchor);
    setQuery('');
    setFocused(false);
  };

  const getTypeIcon = (type: DocSearchResult['type']) => {
    switch (type) {
      case 'endpoint': return '⚡';
      case 'command': return '▶';
      case 'tool': return '🔧';
      default: return '📄';
    }
  };

  return (
    <div class="doc-search" classList={{ focused: focused() }}>
      <div class="search-input-wrapper">
        <span class="search-icon">⌕</span>
        <input
          type="text"
          class="search-input"
          placeholder="Search documentation..."
          value={query()}
          onInput={(e) => setQuery(e.currentTarget.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setTimeout(() => setFocused(false), 200)}
        />
        <Show when={query()}>
          <button
            class="clear-btn"
            onClick={() => setQuery('')}
          >
            ✕
          </button>
        </Show>
        <kbd class="search-shortcut">⌘K</kbd>
      </div>

      <Show when={focused() && results().length > 0}>
        <div class="search-results">
          <For each={results()}>
            {(result) => (
              <button
                class="search-result"
                onClick={() => handleSelect(result)}
              >
                <span class="result-icon">{getTypeIcon(result.type)}</span>
                <div class="result-content">
                  <span class="result-title">{result.title}</span>
                  <span class="result-path">{result.sectionId}</span>
                </div>
              </button>
            )}
          </For>
        </div>
      </Show>

      <Show when={focused() && query().length >= 2 && results().length === 0}>
        <div class="search-results">
          <div class="no-results">
            No results found for "{query()}"
          </div>
        </div>
      </Show>

      <style>{`
        .doc-search {
          position: relative;
          width: 100%;
          max-width: 400px;
        }

        .search-input-wrapper {
          display: flex;
          align-items: center;
          gap: var(--space-2);
          padding: var(--space-2) var(--space-3);
          background: var(--slate-800);
          border: 1px solid var(--slate-700);
          border-radius: var(--radius-md);
          transition: all var(--transition-fast);
        }

        .doc-search.focused .search-input-wrapper {
          border-color: var(--electric-teal);
          box-shadow: 0 0 0 2px rgba(8, 145, 178, 0.2);
        }

        .search-icon {
          color: var(--slate-500);
          font-size: 14px;
        }

        .search-input {
          flex: 1;
          background: transparent;
          border: none;
          color: var(--ghost-slate);
          font-size: var(--text-sm);
          outline: none;
        }

        .search-input::placeholder {
          color: var(--slate-500);
        }

        .clear-btn {
          padding: 0;
          background: transparent;
          border: none;
          color: var(--slate-500);
          cursor: pointer;
          font-size: 12px;
        }

        .clear-btn:hover {
          color: var(--slate-300);
        }

        .search-shortcut {
          padding: var(--space-1) var(--space-2);
          background: var(--slate-700);
          border-radius: var(--radius-sm);
          font-family: var(--font-mono);
          font-size: var(--text-xs);
          color: var(--slate-400);
        }

        .search-results {
          position: absolute;
          top: calc(100% + var(--space-2));
          left: 0;
          right: 0;
          background: var(--slate-800);
          border: 1px solid var(--slate-700);
          border-radius: var(--radius-md);
          box-shadow: var(--shadow-lg);
          max-height: 400px;
          overflow-y: auto;
          z-index: var(--z-dropdown);
        }

        .search-result {
          display: flex;
          align-items: flex-start;
          gap: var(--space-3);
          padding: var(--space-3);
          background: transparent;
          border: none;
          border-bottom: 1px solid var(--slate-700);
          cursor: pointer;
          width: 100%;
          text-align: left;
          transition: background var(--transition-fast);
        }

        .search-result:last-child {
          border-bottom: none;
        }

        .search-result:hover {
          background: var(--slate-700);
        }

        .result-icon {
          font-size: 14px;
          width: 20px;
          text-align: center;
          flex-shrink: 0;
        }

        .result-content {
          flex: 1;
          display: flex;
          flex-direction: column;
          gap: var(--space-1);
          min-width: 0;
        }

        .result-title {
          color: var(--ghost-slate);
          font-size: var(--text-sm);
          font-weight: var(--font-medium);
        }

        .result-path {
          color: var(--slate-500);
          font-size: var(--text-xs);
          font-family: var(--font-mono);
        }

        .no-results {
          padding: var(--space-4);
          text-align: center;
          color: var(--slate-500);
          font-size: var(--text-sm);
        }
      `}</style>
    </div>
  );
};
