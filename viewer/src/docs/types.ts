/**
 * Documentation Types
 */

export interface DocSection {
  id: string;
  title: string;
  icon?: string;
  children?: DocSection[];
}

export interface DocEndpoint {
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'QUERY' | 'MUTATION';
  path: string;
  description: string;
  auth?: string;
  parameters?: DocParameter[];
  requestBody?: DocRequestBody;
  response?: DocResponse;
  example?: DocExample;
}

export interface DocParameter {
  name: string;
  type: string;
  required: boolean;
  default?: string;
  description: string;
}

export interface DocRequestBody {
  contentType: string;
  schema: string;
  example?: string;
}

export interface DocResponse {
  status: number;
  description: string;
  example?: string;
}

export interface DocExample {
  request?: string;
  response?: string;
  description?: string;
}

export interface DocCommand {
  name: string;
  description: string;
  usage: string;
  flags?: DocFlag[];
  examples?: string[];
  subcommands?: DocCommand[];
}

export interface DocFlag {
  name: string;
  short?: string;
  type: string;
  required: boolean;
  default?: string;
  description: string;
}

export interface DocTool {
  name: string;
  description: string;
  inputs: DocParameter[];
  outputs: DocParameter[];
  example?: DocExample;
}

export type DocSearchResult = {
  sectionId: string;
  title: string;
  content: string;
  anchor: string;
  type: 'section' | 'endpoint' | 'command' | 'tool';
};
