/**
 * DocsPage - Main documentation page component
 */

import { Component, createSignal, createMemo, Show, Switch, Match } from 'solid-js';
import { DocNav } from './components/DocNav';
import { DocSearch } from './components/DocSearch';
import { docSections, buildSearchIndex } from './content/index';
import {
  OverviewIntro,
  OverviewConcepts,
  OverviewQuickstart,
  InterfacesRest,
  InterfacesMcp,
  InterfacesGraphql,
  InterfacesCli,
  ManualSimulation,
  ManualViewer,
  ManualAerie,
  ManualTroubleshooting,
  ChangelogSection,
} from './content/sections';

export const DocsPage: Component = () => {
  const [activeSection, setActiveSection] = createSignal('overview-intro');
  const [sidebarCollapsed, setSidebarCollapsed] = createSignal(false);

  const searchIndex = createMemo(() => buildSearchIndex());

  const handleNavigate = (sectionId: string, anchor?: string) => {
    setActiveSection(sectionId);

    // Scroll to anchor if provided
    if (anchor) {
      setTimeout(() => {
        const element = document.getElementById(anchor);
        if (element) {
          element.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      }, 100);
    } else {
      // Scroll to top of content
      const content = document.querySelector('.docs-content');
      if (content) {
        content.scrollTo({ top: 0, behavior: 'smooth' });
      }
    }

    // Update URL hash for deep linking
    window.history.replaceState(null, '', `#${sectionId}`);
  };

  // Handle initial hash on mount
  const initFromHash = () => {
    const hash = window.location.hash.slice(1);
    if (hash) {
      setActiveSection(hash);
    }
  };

  // Call on mount
  if (typeof window !== 'undefined') {
    initFromHash();
  }

  return (
    <div class="docs-page">
      {/* Sidebar */}
      <aside
        class="docs-sidebar"
        classList={{ collapsed: sidebarCollapsed() }}
      >
        <div class="sidebar-header">
          <div class="sidebar-logo">
            <span class="logo-icon">📚</span>
            <Show when={!sidebarCollapsed()}>
              <span class="logo-text">Documentation</span>
            </Show>
          </div>
          <button
            class="collapse-btn"
            onClick={() => setSidebarCollapsed(!sidebarCollapsed())}
            title={sidebarCollapsed() ? 'Expand' : 'Collapse'}
          >
            {sidebarCollapsed() ? '▸' : '◂'}
          </button>
        </div>

        <Show when={!sidebarCollapsed()}>
          <div class="sidebar-search">
            <DocSearch
              searchIndex={searchIndex()}
              onNavigate={handleNavigate}
            />
          </div>
        </Show>

        <DocNav
          sections={docSections}
          activeSection={activeSection()}
          onNavigate={handleNavigate}
        />

        <div class="sidebar-footer">
          <a href="/" class="back-link">
            ← Back to Viewer
          </a>
        </div>
      </aside>

      {/* Main Content */}
      <main class="docs-main">
        <div class="docs-content">
          <Switch>
            {/* Overview */}
            <Match when={activeSection() === 'overview' || activeSection() === 'overview-intro'}>
              <OverviewIntro />
            </Match>
            <Match when={activeSection() === 'overview-concepts'}>
              <OverviewConcepts />
            </Match>
            <Match when={activeSection() === 'overview-quickstart'}>
              <OverviewQuickstart />
            </Match>

            {/* Interfaces */}
            <Match when={activeSection() === 'interfaces' || activeSection() === 'interfaces-rest'}>
              <InterfacesRest />
            </Match>
            <Match when={activeSection() === 'interfaces-mcp'}>
              <InterfacesMcp />
            </Match>
            <Match when={activeSection() === 'interfaces-graphql'}>
              <InterfacesGraphql />
            </Match>
            <Match when={activeSection() === 'interfaces-cli'}>
              <InterfacesCli />
            </Match>

            {/* User Manual */}
            <Match when={activeSection() === 'user-manual' || activeSection() === 'manual-simulation'}>
              <ManualSimulation />
            </Match>
            <Match when={activeSection() === 'manual-viewer'}>
              <ManualViewer />
            </Match>
            <Match when={activeSection() === 'manual-aerie'}>
              <ManualAerie />
            </Match>
            <Match when={activeSection() === 'manual-troubleshooting'}>
              <ManualTroubleshooting />
            </Match>

            {/* Changelog */}
            <Match when={activeSection() === 'changelog'}>
              <ChangelogSection />
            </Match>

            {/* Default */}
            <Match when={true}>
              <OverviewIntro />
            </Match>
          </Switch>
        </div>
      </main>

      <style>{`
        .docs-page {
          display: flex;
          width: 100%;
          height: 100%;
          background: var(--slate-900);
          color: var(--ghost-slate);
        }

        /* Sidebar */
        .docs-sidebar {
          width: 280px;
          min-width: 280px;
          background: var(--deep-space-navy);
          display: flex;
          flex-direction: column;
          border-right: 1px solid var(--slate-700);
          transition: width var(--transition-normal), min-width var(--transition-normal);
        }

        .docs-sidebar.collapsed {
          width: 60px;
          min-width: 60px;
        }

        .sidebar-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: var(--space-4);
          border-bottom: 1px solid var(--slate-700);
          min-height: 56px;
        }

        .sidebar-logo {
          display: flex;
          align-items: center;
          gap: var(--space-3);
        }

        .logo-icon {
          font-size: 20px;
        }

        .logo-text {
          font-size: var(--text-sm);
          font-weight: var(--font-semibold);
          color: var(--ghost-slate);
          white-space: nowrap;
        }

        .collapse-btn {
          padding: var(--space-2);
          background: transparent;
          border: none;
          color: var(--slate-400);
          cursor: pointer;
          border-radius: var(--radius-sm);
          transition: all var(--transition-fast);
        }

        .collapse-btn:hover {
          background: var(--slate-800);
          color: var(--ghost-slate);
        }

        .sidebar-search {
          padding: var(--space-3);
          border-bottom: 1px solid var(--slate-700);
        }

        .sidebar-footer {
          margin-top: auto;
          padding: var(--space-4);
          border-top: 1px solid var(--slate-700);
        }

        .back-link {
          display: flex;
          align-items: center;
          gap: var(--space-2);
          color: var(--slate-400);
          text-decoration: none;
          font-size: var(--text-sm);
          transition: color var(--transition-fast);
        }

        .back-link:hover {
          color: var(--electric-teal);
        }

        /* Main Content */
        .docs-main {
          flex: 1;
          overflow: hidden;
          display: flex;
          flex-direction: column;
        }

        .docs-content {
          flex: 1;
          overflow-y: auto;
          padding: var(--space-8);
          max-width: 900px;
        }

        /* Section Styling */
        .doc-section {
          margin-bottom: var(--space-8);
        }

        .doc-section h2 {
          font-size: var(--text-2xl);
          font-weight: var(--font-bold);
          color: var(--ghost-slate);
          margin: 0 0 var(--space-4) 0;
          padding-bottom: var(--space-3);
          border-bottom: 1px solid var(--slate-700);
        }

        .doc-section h3 {
          font-size: var(--text-lg);
          font-weight: var(--font-semibold);
          color: var(--ghost-slate);
          margin: var(--space-6) 0 var(--space-3) 0;
        }

        .doc-section h4 {
          font-size: var(--text-base);
          font-weight: var(--font-semibold);
          color: var(--slate-200);
          margin: var(--space-4) 0 var(--space-2) 0;
        }

        .doc-section p {
          color: var(--slate-300);
          font-size: var(--text-sm);
          line-height: 1.7;
          margin: var(--space-3) 0;
        }

        .doc-section ul,
        .doc-section ol {
          color: var(--slate-300);
          font-size: var(--text-sm);
          line-height: 1.7;
          margin: var(--space-3) 0;
          padding-left: var(--space-6);
        }

        .doc-section li {
          margin-bottom: var(--space-2);
        }

        .doc-section code {
          background: var(--slate-700);
          padding: 2px 6px;
          border-radius: var(--radius-sm);
          font-family: var(--font-mono);
          font-size: var(--text-xs);
          color: var(--electric-teal);
        }

        .doc-section strong {
          color: var(--ghost-slate);
          font-weight: var(--font-semibold);
        }

        .doc-section a {
          color: var(--electric-teal);
          text-decoration: none;
        }

        .doc-section a:hover {
          text-decoration: underline;
        }

        /* Responsive */
        @media (max-width: 768px) {
          .docs-sidebar {
            position: fixed;
            left: 0;
            top: 0;
            height: 100%;
            z-index: var(--z-modal);
            transform: translateX(-100%);
          }

          .docs-sidebar:not(.collapsed) {
            transform: translateX(0);
          }

          .docs-content {
            padding: var(--space-4);
          }
        }
      `}</style>
    </div>
  );
};
