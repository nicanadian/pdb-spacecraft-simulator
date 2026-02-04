import { requirementOverlay, setRequirementOverlay } from '../stores/modelStore';

export default function RequirementOverlayToggle() {
  const active = () => requirementOverlay();

  return (
    <button
      onClick={() => setRequirementOverlay(!active())}
      title="Toggle requirement badges"
      style={{
        padding: '4px 10px',
        'border-radius': '6px',
        'font-size': '11px',
        background: active() ? '#7c3aed' : '#0f172a',
        color: active() ? '#f1f5f9' : '#94a3b8',
        border: active() ? '1px solid #8b5cf6' : '1px solid #334155',
        cursor: 'pointer',
        'white-space': 'nowrap',
      }}
    >
      REQ
    </button>
  );
}
