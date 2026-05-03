export interface MpcToolContent {
  type: string;
  text?: string;
}

export interface CgcMcpToolResponse {
  content?: MpcToolContent[];
}

export interface CgcTool {
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
}

export interface IndexedRepository {
  repo_name?: string;
  path?: string;
  file_count?: number;
}

export interface DeadCodeEntry {
  function_name?: string;
  path?: string;
  line_number?: number;
  class_name?: string;
}

export interface CallerEntry {
  caller_name?: string;
  caller_file_path?: string;
  caller_line_number?: number;
  call_line_number?: number;
}

export interface CalleeEntry {
  called_name?: string;
  called_file_path?: string;
  called_line_number?: number;
}

export interface ComplexityEntry {
  function_name?: string;
  path?: string;
  cyclomatic_complexity?: number; // stored in some tool responses
  complexity?: number;            // alias: Python returns 'as complexity'
  line_number?: number;
}
