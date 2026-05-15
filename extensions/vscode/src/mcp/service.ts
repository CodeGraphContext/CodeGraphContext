import * as vscode from "vscode";
import { CgcMcpClient } from "./client";
import {
  CalleeEntry,
  CallerEntry,
  ComplexityEntry,
  DeadCodeEntry,
  DiscoveredContext,
  IndexedRepository,
  JobStatus,
  RepoStats,
} from "../types/cgc";

export class CgcService {
  constructor(private readonly client: CgcMcpClient) {}

  public getRepoPathOverride(): string | undefined {
    const repoPath = vscode.workspace.getConfiguration("cgc").get<string>("repoPath", "").trim();
    return repoPath || undefined;
  }

  // ─── Dead Code ───────────────────────────────────────────────────────────────

  public async findDeadCode(): Promise<DeadCodeEntry[]> {
    const res = await this.client.callTool<{
      potentially_unused_functions?: DeadCodeEntry[];
      results?: { potentially_unused_functions?: DeadCodeEntry[] };
    }>("find_dead_code", {
      repo_path: this.getRepoPathOverride()
    });
    return res.potentially_unused_functions ?? res.results?.potentially_unused_functions ?? [];
  }

  // ─── Complexity ───────────────────────────────────────────────────────────────

  public async getComplexity(functionName: string, filePath?: string): Promise<number | undefined> {
    const res = await this.client.callTool<{ cyclomatic_complexity?: number; results?: { complexity?: number; cyclomatic_complexity?: number } }>("calculate_cyclomatic_complexity", {
      function_name: functionName,
      path: filePath,
      repo_path: this.getRepoPathOverride()
    });
    return res.cyclomatic_complexity ?? res.results?.complexity ?? res.results?.cyclomatic_complexity;
  }

  public async getComplexityHotspots(limit = 10): Promise<ComplexityEntry[]> {
    const res = await this.client.callTool<{
      results?: Array<{ function_name?: string; path?: string; complexity?: number; cyclomatic_complexity?: number; line_number?: number }>;
      functions?: ComplexityEntry[];
      most_complex_functions?: ComplexityEntry[];
    }>("find_most_complex_functions", {
      limit,
      repo_path: this.getRepoPathOverride()
    });
    const raw = res.results ?? res.functions ?? res.most_complex_functions ?? [];
    return raw.map(r => ({
      function_name: r.function_name,
      path: r.path,
      line_number: r.line_number,
      cyclomatic_complexity: r.cyclomatic_complexity ?? r.complexity,
      complexity: r.complexity ?? r.cyclomatic_complexity
    }));
  }

  // ─── Relationships ────────────────────────────────────────────────────────────

  public async findCallers(target: string, filePath?: string): Promise<CallerEntry[]> {
    const res = await this.client.callTool<{ callers?: CallerEntry[]; results?: any }>("analyze_code_relationships", {
      query_type: "find_callers",
      target,
      context: filePath,
      repo_path: this.getRepoPathOverride()
    });
    let data: any[] = [];
    if (Array.isArray(res.callers)) data = res.callers;
    else if (Array.isArray(res.results)) data = res.results;
    else data = res.results?.results ?? [];

    return data.map(item => ({
      caller_name: item.caller_name ?? item.caller_function ?? item.name,
      caller_file_path: item.caller_file_path ?? item.path,
      caller_line_number: item.caller_line_number ?? item.line_number,
      call_line_number: item.call_line_number
    }));
  }

  public async findCallees(target: string, filePath?: string): Promise<CalleeEntry[]> {
    const res = await this.client.callTool<{ callees?: CalleeEntry[]; results?: any }>("analyze_code_relationships", {
      query_type: "find_callees",
      target,
      context: filePath,
      repo_path: this.getRepoPathOverride()
    });
    let data: any[] = [];
    if (Array.isArray(res.callees)) data = res.callees;
    else if (Array.isArray(res.results)) data = res.results;
    else data = res.results?.results ?? [];

    return data.map(item => ({
      called_name: item.called_name ?? item.called_function ?? item.name,
      called_file_path: item.called_file_path ?? item.path,
      called_line_number: item.called_line_number ?? item.line_number
    }));
  }

  public async listCallees(target: string, filePath?: string, depth = 1): Promise<Array<Record<string, unknown>>> {
    const queryType = depth > 1 ? "find_all_callees" : "find_callees";
    const res = await this.client.callTool<{
      callees?: Array<Record<string, unknown>>;
      results?: Array<Record<string, unknown>> | { results?: Array<Record<string, unknown>> };
    }>("analyze_code_relationships", {
      query_type: queryType,
      target,
      context: filePath,
      depth,
      repo_path: this.getRepoPathOverride()
    });
    if (Array.isArray(res.callees)) return res.callees;
    if (Array.isArray(res.results)) return res.results;
    return (res.results as { results?: Array<Record<string, unknown>> })?.results ?? [];
  }

  public async findCallChain(from: string, to: string, fromFile?: string, toFile?: string): Promise<Array<Record<string, unknown>>> {
    const target = `${from}->${to}`;
    const context = (fromFile || toFile) ? `${fromFile ?? ""}|${toFile ?? ""}` : undefined;
    const res = await this.client.callTool<{
      chain?: Array<Record<string, unknown>>;
      results?: Array<Record<string, unknown>>;
      data?: Array<Record<string, unknown>>;
    }>("analyze_code_relationships", {
      query_type: "call_chain",
      target,
      context,
      repo_path: this.getRepoPathOverride()
    });
    return res.chain ?? (Array.isArray(res.results) ? res.results : []) ?? res.data ?? [];
  }

  public async findImporters(target: string, filePath?: string): Promise<Array<Record<string, unknown>>> {
    const res = await this.client.callTool<{
      importers?: Array<Record<string, unknown>>;
      results?: Array<Record<string, unknown>>;
    }>("analyze_code_relationships", {
      query_type: "find_importers",
      target,
      context: filePath,
      repo_path: this.getRepoPathOverride()
    });
    if (Array.isArray(res.importers)) return res.importers;
    if (Array.isArray(res.results)) return res.results;
    return [];
  }

  public async findModuleDeps(target: string, filePath?: string): Promise<Array<Record<string, unknown>>> {
    const res = await this.client.callTool<{
      dependencies?: Array<Record<string, unknown>>;
      results?: Array<Record<string, unknown>>;
    }>("analyze_code_relationships", {
      query_type: "module_deps",
      target,
      context: filePath,
      repo_path: this.getRepoPathOverride()
    });
    if (Array.isArray(res.dependencies)) return res.dependencies;
    if (Array.isArray(res.results)) return res.results;
    return [];
  }

  public async findClassHierarchy(target: string, filePath?: string): Promise<Array<Record<string, unknown>>> {
    const res = await this.client.callTool<{
      hierarchy?: Array<Record<string, unknown>>;
      results?: Array<Record<string, unknown>>;
    }>("analyze_code_relationships", {
      query_type: "class_hierarchy",
      target,
      context: filePath,
      repo_path: this.getRepoPathOverride()
    });
    if (Array.isArray(res.hierarchy)) return res.hierarchy;
    if (Array.isArray(res.results)) return res.results;
    return [];
  }

  public async findFunctionsByDecorator(decorator: string): Promise<Array<Record<string, unknown>>> {
    const res = await this.client.callTool<{
      results?: Array<Record<string, unknown>>;
      functions?: Array<Record<string, unknown>>;
    }>("analyze_code_relationships", {
      query_type: "find_functions_by_decorator",
      target: decorator,
      repo_path: this.getRepoPathOverride()
    });
    if (Array.isArray(res.functions)) return res.functions;
    if (Array.isArray(res.results)) return res.results;
    return [];
  }

  public async variableImpactRadius(target: string, filePath?: string): Promise<Array<Record<string, unknown>>> {
    const res = await this.client.callTool<{
      variable_impact?: Array<Record<string, unknown>>;
      usages?: Array<Record<string, unknown>>;
      results?: Array<Record<string, unknown>> | { results?: { instances?: Array<Record<string, unknown>> } };
    }>("analyze_code_relationships", {
      query_type: "variable_scope",
      target,
      context: filePath,
      repo_path: this.getRepoPathOverride()
    });
    if (Array.isArray(res.results)) return res.results;
    return res.variable_impact ?? res.usages ?? res.results?.results?.instances ?? [];
  }

  // ─── Repositories & Context ───────────────────────────────────────────────────

  public async listRepositories(): Promise<IndexedRepository[]> {
    const res = await this.client.callTool<{ repositories?: IndexedRepository[]; results?: IndexedRepository[] }>("list_indexed_repositories", {});
    const rows = res.repositories ?? res.results ?? [];
    return rows.map((r) => ({
      repo_name: r.repo_name ?? (r as Record<string, unknown>).name as string | undefined,
      path: r.path,
      file_count: r.file_count
    }));
  }

  public async getRepoStats(repoPath?: string): Promise<RepoStats> {
    const res = await this.client.callTool<{
      stats?: RepoStats;
      results?: RepoStats;
      file_count?: number;
      function_count?: number;
      class_count?: number;
      module_count?: number;
      total_files?: number;
      total_functions?: number;
      total_classes?: number;
    }>("get_repository_stats", {
      repo_path: repoPath ?? this.getRepoPathOverride()
    });
    // normalise multiple possible shapes
    const base = res.stats ?? res.results ?? res;
    return {
      repo_path: repoPath,
      file_count: base.file_count ?? base.total_files,
      function_count: base.function_count ?? base.total_functions,
      class_count: base.class_count ?? base.total_classes,
      module_count: base.module_count,
    };
  }

  public async discoverContexts(path?: string): Promise<DiscoveredContext[]> {
    const res = await this.client.callTool<{
      contexts?: DiscoveredContext[];
      results?: DiscoveredContext[];
    }>("discover_codegraph_contexts", {
      path,
      max_depth: 2
    });
    return res.contexts ?? res.results ?? [];
  }

  public async switchContext(contextPath: string): Promise<void> {
    await this.client.callTool("switch_context", { context_path: contextPath, save: true });
  }

  // ─── Watches ─────────────────────────────────────────────────────────────────

  public async listWatches(): Promise<string[]> {
    const res = await this.client.callTool<{ watched_paths?: string[] }>("list_watched_paths", {});
    return res.watched_paths ?? [];
  }

  public async watchWorkspace(path: string): Promise<void> {
    await this.client.callTool("watch_directory", { path });
  }

  public async indexWorkspace(path: string): Promise<string | undefined> {
    const res = await this.client.callTool<{ job_id?: string; jobId?: string }>("add_code_to_graph", { path });
    return res.job_id ?? res.jobId;
  }

  // ─── Jobs ─────────────────────────────────────────────────────────────────────

  public async checkJobStatus(jobId: string): Promise<JobStatus> {
    const res = await this.client.callTool<{
      job_id?: string;
      status?: string;
      progress?: number;
      message?: string;
      error?: string;
    }>("check_job_status", { job_id: jobId });
    return {
      job_id: res.job_id ?? jobId,
      status: (res.status as JobStatus["status"]) ?? "pending",
      progress: res.progress,
      message: res.message,
      error: res.error,
    };
  }

  // ─── Bundles ──────────────────────────────────────────────────────────────────

  public async searchBundles(query: string): Promise<Array<Record<string, unknown>>> {
    const res = await this.client.callTool<{ bundles?: Array<Record<string, unknown>>; results?: Array<Record<string, unknown>> }>("search_registry_bundles", {
      query,
      unique_only: true
    });
    return res.bundles ?? res.results ?? [];
  }

  public async loadBundle(bundleName: string): Promise<void> {
    await this.client.callTool("load_bundle", { bundle_name: bundleName });
  }

  // ─── Code Search ─────────────────────────────────────────────────────────────

  public async findCode(query: string, fuzzySearch = true): Promise<Array<Record<string, unknown>>> {
    const res = await this.client.callTool<{
      results?: Array<Record<string, unknown>> | { ranked_results?: Array<Record<string, unknown>> };
      matches?: Array<Record<string, unknown>>;
    }>("find_code", {
      query,
      fuzzy_search: fuzzySearch,
      repo_path: this.getRepoPathOverride()
    });
    if (Array.isArray(res.results)) return res.results;
    return res.results?.ranked_results ?? res.matches ?? [];
  }

  // ─── Listing ──────────────────────────────────────────────────────────────────

  public async listFunctions(repoPath?: string): Promise<Array<Record<string, unknown>>> {
    const res = await this.client.callTool<{
      functions?: Array<Record<string, unknown>>;
      results?: Array<Record<string, unknown>>;
    }>("find_most_complex_functions", { limit: 200, repo_path: repoPath ?? this.getRepoPathOverride() });
    return res.functions ?? res.results ?? [];
  }

  public async listClasses(repoPath?: string): Promise<Array<Record<string, unknown>>> {
    const res = await this.client.callTool<{
      data?: Array<Record<string, unknown>>;
      results?: Array<Record<string, unknown>>;
    }>("execute_cypher_query", {
      cypher_query: "MATCH (c:Class) RETURN c.name AS name, c.file_path AS path, c.line_number AS line ORDER BY c.name LIMIT 200"
    });
    return res.data ?? res.results ?? [];
  }

  public async listImports(file: string): Promise<Array<Record<string, unknown>>> {
    const res = await this.client.callTool<{
      data?: Array<Record<string, unknown>>;
      results?: Array<Record<string, unknown>>;
    }>("execute_cypher_query", {
      cypher_query: `MATCH (f:File {path: '${file.replace(/'/g, "\\'")}'})-[*1]->(i:Import) RETURN i.name AS name, i.source AS source LIMIT 100`
    });
    return res.data ?? res.results ?? [];
  }

  // ─── Raw Cypher ───────────────────────────────────────────────────────────────

  public async runCypher(cypherQuery: string): Promise<Array<Record<string, unknown>>> {
    const res = await this.client.callTool<{ data?: Array<Record<string, unknown>>; results?: Array<Record<string, unknown>> }>("execute_cypher_query", {
      cypher_query: cypherQuery
    });
    return res.data ?? res.results ?? [];
  }

  // ─── Report ───────────────────────────────────────────────────────────────────

  public async generateReport(outputPath?: string): Promise<string> {
    const res = await this.client.callTool<{
      output_path?: string;
      report_path?: string;
      message?: string;
    }>("generate_report", {
      output_path: outputPath,
      include_java: false,
      god_node_limit: 15,
      complexity_limit: 15,
      cross_module_limit: 20,
    });
    return res.output_path ?? res.report_path ?? outputPath ?? "CGC_REPORT.md";
  }
}
