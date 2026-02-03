# Mission Visualization Viewer

Web-based mission visualization UI built with SolidJS and CesiumJS.

## Quick Start

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Open in browser
# Viewer: http://localhost:3002?run=../runs/<run-id>
# Docs:   http://localhost:3002?page=docs
```

## Features

- **3D Orbit Visualization** — CesiumJS-powered spacecraft trajectory display
- **5 Task-Oriented Workspaces** — Mission Overview, Maneuver Planning, VLEO & Lifetime, Anomaly Response, Payload Ops
- **Timeline Controls** — Playback, scrubbing, speed adjustment (1x-1000x)
- **Alert System** — Color-coded severity indicators with causal linking
- **Built-in Documentation** — Complete API and user manual accessible via `?page=docs`

## URL Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `run` | Path to simulation run directory | `?run=../runs/20250115_LOW` |
| `page` | Page to display | `?page=docs` |

## Documentation Page

The built-in documentation page (`?page=docs`) includes:

- **Overview** — Introduction, key concepts, quickstart
- **Interfaces** — REST API, MCP Tools, Aerie GraphQL, CLI
- **User Manual** — Workflow guides, viewer usage, troubleshooting
- **Changelog** — Version history and planned changes

### Updating Documentation

Documentation content is in `src/docs/content/`:

1. **Add a new section**: Edit `docSections` in `content/index.ts`, create section component in `content/sections.tsx`, add `Match` case in `DocsPage.tsx`

2. **Add REST endpoint**: Add to `restEndpoints` array in `content/index.ts`

3. **Add MCP tool**: Add to `mcpTools` array in `content/index.ts`

4. **Add CLI command**: Add to `cliCommands` array in `content/index.ts`

## Development

```bash
# Start dev server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## Design System

The viewer uses a custom design system defined in `src/styles/`:

- **tokens.css** — Color palette, typography, spacing, elevation
- **global.css** — Base styles, utilities, form controls
- **glass.css** — Glassmorphism component library

Key colors:
- Deep Space Navy: `#0F172A` (backgrounds)
- Electric Teal: `#0891B2` (accents, active states)
- Ghost Slate: `#F8FAFC` (primary text)

## Architecture

```
src/
├── components/
│   ├── shell/          # App shell, header, footer, navigation
│   ├── geometry/       # CesiumJS 3D viewport
│   ├── timeline/       # Timeline visualization
│   ├── alerts/         # Alert system
│   └── shared/         # Reusable components
├── workspaces/         # 5 task-oriented workspace layouts
├── stores/             # SolidJS state management
├── services/           # Data loading, Cesium integration
├── docs/               # Built-in documentation
│   ├── components/     # Doc UI components
│   └── content/        # Documentation content
├── styles/             # Design tokens and global CSS
└── types/              # TypeScript type definitions
```
