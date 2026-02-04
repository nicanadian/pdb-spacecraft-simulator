import { Show, Switch, Match, onMount } from 'solid-js';
import {
  graph, setGraph,
  loading, setLoading,
  error, setError,
  activeView, setActiveView,
  activeViewpoint,
  selectedNode,
  hasArchModel,
  archModel,
} from './stores/modelStore';
import { loadModelData } from './services/dataLoader';
import SearchBar from './components/SearchBar';
import FilterPanel from './components/FilterPanel';
import NodeDetail from './components/NodeDetail';
import ViewpointSelector from './components/ViewpointSelector';
import HierarchyNav from './components/HierarchyNav';
import LevelSelector from './components/LevelSelector';
import RequirementOverlayToggle from './components/RequirementOverlayToggle';
import ArchitectureView from './views/ArchitectureView';
import OperationalContextView from './views/OperationalContextView';
import CapabilityMapView from './views/CapabilityMapView';
import LogicalArchitectureView from './views/LogicalArchitectureView';
import InterfaceContractsView from './views/InterfaceContractsView';
import TechnicalDeploymentView from './views/TechnicalDeploymentView';
import RequirementsView from './views/RequirementsView';
import GuaranteesView from './views/GuaranteesView';
import ImpactView from './views/ImpactView';

export default function App() {
  onMount(async () => {
    try {
      await loadModelData();
      setLoading(false);
    } catch (err: any) {
      setError(err.message ?? 'Failed to load model');
      setLoading(false);
    }
  });

  const gitSha = () => {
    const model = archModel();
    if (model?.metadata?.git_sha) return String(model.metadata.git_sha);
    const g = graph();
    if (g?.metadata?.git_sha) return String(g.metadata.git_sha);
    return null;
  };

  const nodeCount = () => {
    const model = archModel();
    if (model) return model.architecture.nodes.length;
    return graph()?.nodes.length ?? 0;
  };

  const edgeCount = () => {
    const model = archModel();
    if (model) return model.architecture.edges.length;
    return graph()?.edges.length ?? 0;
  };

  return (
    <div style={{ display: 'flex', 'flex-direction': 'column', height: '100vh', background: '#0f172a' }}>
      {/* Header */}
      <header style={{
        height: '56px',
        background: '#1e293b',
        'border-bottom': '1px solid #334155',
        display: 'flex',
        'align-items': 'center',
        padding: '0 16px',
        gap: '12px',
        'flex-shrink': '0',
      }}>
        <span style={{ 'font-size': '14px', 'font-weight': '600', color: '#f1f5f9', 'white-space': 'nowrap' }}>
          Architecture Browser
        </span>
        <Show when={!loading() && !error()}>
          <span style={{ 'font-size': '12px', color: '#64748b', 'white-space': 'nowrap' }}>
            {nodeCount()} nodes &middot; {edgeCount()} edges
          </span>
        </Show>
        <div style={{ flex: '1' }} />
        <Show when={hasArchModel()}>
          <ViewpointSelector />
          <LevelSelector />
          <RequirementOverlayToggle />
        </Show>
        {/* Fallback tabs for v1 */}
        <Show when={!hasArchModel() && !loading()}>
          <NavTab label="Architecture" view="architecture" />
          <NavTab label="Guarantees" view="guarantees" />
          <NavTab label="Impact" view="impact" />
        </Show>
        <Show when={gitSha()}>
          <span style={{ 'font-size': '11px', color: '#475569', 'font-family': 'monospace' }}>
            {gitSha()}
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
        <Show when={!loading() && !error()}>
          {/* Left Sidebar */}
          <div style={{
            width: '280px',
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
            <Show when={hasArchModel()}>
              <HierarchyNav />
            </Show>
            <FilterPanel />
          </div>

          {/* Main Content */}
          <div style={{ flex: '1', overflow: 'hidden' }}>
            <Show when={hasArchModel()} fallback={
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
            }>
              <Switch>
                <Match when={activeViewpoint() === 'operational-context'}>
                  <OperationalContextView />
                </Match>
                <Match when={activeViewpoint() === 'capability-map'}>
                  <CapabilityMapView />
                </Match>
                <Match when={activeViewpoint() === 'logical-architecture'}>
                  <LogicalArchitectureView />
                </Match>
                <Match when={activeViewpoint() === 'interface-contracts'}>
                  <InterfaceContractsView />
                </Match>
                <Match when={activeViewpoint() === 'technical-deployment'}>
                  <TechnicalDeploymentView />
                </Match>
                <Match when={activeViewpoint() === 'requirements-decomposition'}>
                  <RequirementsView />
                </Match>
              </Switch>
            </Show>
          </div>

          {/* Right Sidebar (conditional) */}
          <Show when={selectedNode()}>
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
