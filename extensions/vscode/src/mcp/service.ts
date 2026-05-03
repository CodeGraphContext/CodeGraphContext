import * as vscode from "vscode";
import { CgcMcpClient } from "./client";
import { CalleeEntry, CallerEntry, ComplexityEntry, DeadCodeEntry, IndexedRepository } from "../types/cgc";

export class CgcService {
  constructor(private readonly client: CgcMcpClient) {}

  public getRepoPathOverride(): string | undefined {
    const repoPath = vscode.workspace.getConfiguration("cgc").get<string>("repoPath", "").trim();
    return repoPath || undefined;
  }

  public async findDeadCode(): Promise<DeadCodeEntry[]> {
    const res = await this.client.callTool<{
      potentially_unused_functions?: DeadCodeEntry[];
      results?: { potentially_unused_functions?: DeadCodeEntry[] };
    }>("find_dead_code", {
      repo_path: this.getRepoPathOverride()
    });
    return res.potentially_unused_functions ?? res.results?.potentially_unused_functions ?? [];
  }

  public async getComplexity(functionName: string, filePath?: string): Promise<number | undefined> {
    const res = await this.client.callTool<{ cyclomatic_complexity?: number; results?: { complexity?: number; cyclomatic_complexity?: number } }>("calculate_cyclomatic_complexity", {
      function_name: functionName,
      path: filePath,
      repo_path: this.getRepoPathOverride()
    });
    return res.cyclomatic_complexity ?? res.results?.complexity ?? res.results?.cyclomatic_complexity;
  }

  public async findCallers(target: string, filePath?: string): Promise<CallerEntry[]> {
    const res = await this.client.callTool<{ callers?: CallerEntry[]; results?: CallerEntry[] | { results?: CallerEntry[] } }>("analyze_code_relationships", {
      query_type: "find_callers",
      target,
      context: filePath,
      repo_path: this.getRepoPathOverride()
    });
    if (Array.isArray(res.callers)) return res.callers;
    if (Array.isArray(res.results)) return res.results;
    return (res.results as { results?: CallerEntry[] })?.results ?? [];
  }

  public async findCallees(target: string, filePath?: string): Promise<CalleeEntry[]> {
    const res = await this.client.callTool<{ callees?: CalleeEntry[]; results?: CalleeEntry[] | { results?: CalleeEntry[] } }>("analyze_code_relationships", {
      query_type: "find_callees",
      target,
      context: filePath,
      repo_path: this.getRepoPathOverride()
    });
    if (Array.isArray(res.callees)) return res.callees;
    if (Array.isArray(res.results)) return res.results;
    return (res.results as { results?: CalleeEntry[] })?.results ?? [];
  }

  public async listRepositories(): Promise<IndexedRepository[]> {
    const res = await this.client.callTool<{ repositories?: IndexedRepository[]; results?: IndexedRepository[] }>("list_indexed_repositories", {});
    const rows = res.repositories ?? res.results ?? [];
    return rows.map((r) => ({
      repo_name: r.repo_name ?? (r as Record<string, unknown>).name as string | undefined,
      path: r.path,
      file_count: r.file_count
    }));
  }

  public async listWatches(): Promise<string[]> {
    const res = await this.client.callTool<{ watched_paths?: string[] }>("list_watched_paths", {});
    return res.watched_paths ?? [];
  }

  public async searchBundles(query: string): Promise<Array<Record<string, unknown>>> {
    const res = await this.client.callTool<{ bundles?: Array<Record<string, unknown>>; results?: Array<Record<string, unknown>> }>("search_registry_bundles", {
      query,
      unique_only: true
    });
    return res.bundles ?? res.results ?? [];
  }

  public async watchWorkspace(path: string): Promise<void> {
    await this.client.callTool("watch_directory", { path });
  }

  public async indexWorkspace(path: string): Promise<void> {
    await this.client.callTool("add_code_to_graph", { path });
  }

  public async runCypher(cypherQuery: string): Promise<Array<Record<string, unknown>>> {
    const res = await this.client.callTool<{ data?: Array<Record<string, unknown>>; results?: Array<Record<string, unknown>> }>("execute_cypher_query", {
      cypher_query: cypherQuery
    });
    return res.data ?? res.results ?? [];
  }

  public async findCode(query: string, fuzzySearch = true): Promise<Array<Record<string, unknown>>> {
    const res = await this.client.callTool<{
      results?: Array<Record<string, unknown>> | { ranked_results?: Array<Record<string, unknown>> };
      matches?: Array<Record<string, unknown>>;
    }>("find_code", {
      query,
      fuzzy_search: fuzzySearch,
      repo_path: this.getRepoPathOverride()
    });
    if (Array.isArray(res.results)) {
      return res.results;
    }
    return res.results?.ranked_results ?? res.matches ?? [];
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
    // Python handler returns { results: [{function_name, path, complexity, line_number}] }
    // 'complexity' is the alias for cyclomatic_complexity in the Cypher RETURN clause
    const raw = res.results ?? res.functions ?? res.most_complex_functions ?? [];
    return raw.map(r => ({
      function_name: r.function_name,
      path: r.path,
      line_number: r.line_number,
      cyclomatic_complexity: r.cyclomatic_complexity ?? r.complexity,
      complexity: r.complexity ?? r.cyclomatic_complexity
    }));
  }

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
      cypher_query: `MATCH (f:File {path: '${file.replace(/'/g, "\\'")}'})-->(i:Import) RETURN i.name AS name, i.source AS source LIMIT 100`
    });
    return res.data ?? res.results ?? [];
  }

  public async findCallChain(from: string, to: string, fromFile?: string, toFile?: string): Promise<Array<Record<string, unknown>>> {
    // The MCP tool expects target in "start->end" format for call_chain queries.
    // Optionally pass context as "fromFile->toFile" for file-scoped search.
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

  public async listCallees(target: string, filePath?: string, depth = 1): Promise<Array<Record<string, unknown>>> {
    // find_all_callees does transitive resolution; find_callees is single-level
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
    if (Array.isArray(res.results)) {
      return res.results;
    }
    return res.variable_impact ?? res.usages ?? res.results?.results?.instances ?? [];
  }
}
