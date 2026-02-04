import { searchQuery, setSearchQuery } from '../stores/modelStore';

export default function SearchBar() {
  return (
    <div style={{
      padding: '0 16px',
    }}>
      <input
        type="text"
        placeholder="Search nodes..."
        value={searchQuery()}
        onInput={(e) => setSearchQuery(e.currentTarget.value)}
        style={{
          width: '100%',
          padding: '8px 12px',
          background: '#1e293b',
          border: '1px solid #334155',
          'border-radius': '6px',
          color: '#e2e8f0',
          'font-size': '13px',
          outline: 'none',
        }}
      />
    </div>
  );
}
