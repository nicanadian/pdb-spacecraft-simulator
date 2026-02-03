/**
 * Documentation Module
 *
 * This module provides a comprehensive documentation page for the spacecraft simulator.
 *
 * ## Structure
 * - `DocsPage.tsx` - Main documentation page component
 * - `components/` - Reusable documentation UI components
 *   - `CodeBlock.tsx` - Syntax-highlighted code with copy-to-clipboard
 *   - `DocNav.tsx` - Left navigation sidebar
 *   - `DocSearch.tsx` - Search across documentation
 *   - `EndpointDoc.tsx` - REST/GraphQL endpoint documentation
 *   - `CommandDoc.tsx` - CLI command documentation
 * - `content/` - Documentation content
 *   - `index.ts` - Navigation structure and interface definitions
 *   - `sections.tsx` - Content section components
 * - `types.ts` - TypeScript types for documentation
 *
 * ## How to Update Documentation
 *
 * ### Adding a new section:
 * 1. Add the section to `docSections` in `content/index.ts`
 * 2. Create the section component in `content/sections.tsx`
 * 3. Add a `Match` case in `DocsPage.tsx`
 *
 * ### Adding a new REST endpoint:
 * 1. Add the endpoint to `restEndpoints` in `content/index.ts`
 * 2. The endpoint will automatically appear in the Interfaces > REST API section
 *
 * ### Adding a new MCP tool:
 * 1. Add the tool to `mcpTools` in `content/index.ts`
 * 2. The tool will automatically appear in the Interfaces > MCP Tools section
 *
 * ### Adding a new CLI command:
 * 1. Add the command to `cliCommands` in `content/index.ts`
 * 2. Use the `subcommands` array for nested commands
 *
 * ## Content Sourcing
 *
 * Documentation is derived from:
 * - `sim_mcp/http_server.py` - REST endpoints
 * - `sim_mcp/server.py` and `sim_mcp/tools/` - MCP tools
 * - `cli/simrun.py` - CLI commands
 * - `sim/io/aerie_client.py` and `sim/io/aerie_queries.py` - Aerie GraphQL
 *
 * When interfaces change, update the corresponding arrays in `content/index.ts`.
 */

export { DocsPage } from './DocsPage';
export * from './types';
export * from './content/index';
