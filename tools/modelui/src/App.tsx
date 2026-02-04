import { createEffect, Show, Switch, Match, onMount } from 'solid-js';
import {
  graph, setGraph,
  loading, setLoading,
  error, setError,
  activeView, setActiveView,
  selectedNode,
} from './stores/modelStore';
import { loadModelGraph } from './services/dataLoader';
import SearchBar from './components/SearchBar';
import FilterPanel from './components/FilterPanel';
import NodeDetail from './components/NodeDetail';
import ArchitectureView from './views/ArchitectureView';
import GuaranteesView from './views/GuaranteesView';
import ImpactView from './views/ImpactView';

export default function App() {
  onMount(async () => {
    try {
      const data = await loadModelGraph();
      setGraph(data);
      setLoading(false);
    } catch (err: any) {
      setError(err.message ?? 'Failed to load model');
      setLoading(false);
    }
  });

  return (
    <div style={{ display: 'flex', 'flex-direction': 'column', height: '100vh', background: '#0f172a' }}>
      {/* Header */}
      <header style={{
        height: '48px',
        background: '#1e293b',
        'border-bottom': '1px solid #334155',
        display: 'flex',
        'align-items': 'center',
        padding: '0 16px',
        gap: '16px',
        'flex-shrink': '0',
      }}>
        <span style={{ 'font-size': '14px', 'font-weight': '600', color: '#f1f5f9' }}>
          Architecture Viewer
        </span>
        <Show when={graph()}>
          <span style={{ 'font-size': '12px', color: '#64748b' }}>
            {graph()!.nodes.length} nodes &middot; {graph()!.edges.length} edges
          </span>
        </Show>
        <div style={{ flex: '1' }} />
        <NavTab label="Architecture" view="architecture" />
        <NavTab label="Guarantees" view="guarantees" />
        <NavTab label="Impact" view="impact" />
        <Show when={graph()?.metadata?.git_sha}>
          <span style={{ 'font-size': '11px', color: '#475569', 'font-family': 'monospace' }}>
            {String(graph()!.metadata.git_sha)}
          </span>
        </Show>
      </header>

      {/* Body */}
      <div style={{ flex: '1', display: 'flex', overflow: 'hidden' }}>
        <Show when={loading()}>
          <div style={{ display: 'flex', 'align-items': 'center', 'justify-content': 'center', width: '100%', color: '#94a3b8' }}>
            Loading...
          </div>
        </Show>
        <Show when={error()}>
          <div style={{ display: 'flex', 'align-items': 'center', 'justify-content': 'center', width: '100%', color: '#ef4444' }}>
            Error: {error()}
          </div>
        </Show>
        <Show when={!loading() && !error() && graph()}>
          {/* Sidebar */}
          <div style={{
            width: '220px',
            background: '#1e293b',
            'border-right': '1px solid #334155',
            display: 'flex',
            'flex-direction': 'column',
            gap: '16px',
            'padding-top': '12px',
            overflow: 'auto',
            'flex-shrink': '0',
          }}>
            <SearchBar />
            <FilterPanel />
          </div>

          {/* Main content */}
          <div style={{ flex: '1', overflow: 'hidden' }}>
            <Switch>
              <Match when={activeView() === 'architecture'}>
                <ArchitectureView />
              </Match>
              <Match when={activeView() === 'guarantees'}>
                <GuaranteesView />
              </Match>
              <Match when={activeView() === 'impact'}>
                <ImpactView />
              </Match>
            </Switch>
          </div>

          {/* Node detail panel */}
          <Show when={activeView() === 'architecture' && selectedNode()}>
            <NodeDetail />
          </Show>
        </Show>
      </div>
    </div>
  );
}

function NavTab(props: { label: string; view: 'architecture' | 'guarantees' | 'impact' }) {
  const active = () => activeView() === props.view;
  return (
    <button
      onClick={() => setActiveView(props.view)}
      style={{
        padding: '6px 14px',
        'border-radius': '6px',
        'font-size': '13px',
        background: active() ? '#334155' : 'transparent',
        color: active() ? '#f1f5f9' : '#94a3b8',
        border: 'none',
        cursor: 'pointer',
        'font-weight': active() ? '500' : '400',
      }}
    >
      {props.label}
    </button>
  );
}
