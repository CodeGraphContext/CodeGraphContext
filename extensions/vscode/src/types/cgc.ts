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

export interface RepoStats {
  repo_path?: string;
  file_count?: number;
  function_count?: number;
  class_count?: number;
  module_count?: number;
  // overall DB stats shape
  total_files?: number;
  total_functions?: number;
  total_classes?: number;
  total_modules?: number;
}

export interface JobStatus {
  job_id: string;
  status: "pending" | "running" | "completed" | "failed";
  progress?: number;
  message?: string;
  error?: string;
}

export interface DiscoveredContext {
  path: string;
  name?: string;
}

export type CgcEventType =
  | "index:started"
  | "index:progress"
  | "index:done"
  | "index:failed"
  | "graph:changed"
  | "repo:changed"
  | "context:changed"
  | "mcp:online"
  | "mcp:offline";

export interface CgcEvent {
  type: CgcEventType;
  payload?: unknown;
}
