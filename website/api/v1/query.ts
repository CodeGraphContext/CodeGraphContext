// website/api/v1/query.ts
import { createClient } from "@supabase/supabase-js";

function extractSessionToken(args: Record<string, unknown> | null | undefined): string {
  if (!args || typeof args !== "object") return "";
  const direct = args.session_id ?? args.sessionId ?? args.session ?? args.cgc_session_id;
  if (direct != null && String(direct).trim()) return String(direct).trim().toLowerCase();
  const sessionLabel = /\bsession[:\s]+([a-z0-9]{6})\b/i;
  for (const value of Object.values(args)) {
    if (typeof value !== "string" || !value.trim()) continue;
    const labeled = value.match(sessionLabel);
    if (labeled?.[1]) return labeled[1].toLowerCase();
  }
  for (const value of Object.values(args)) {
    if (typeof value !== "string") continue;
    const trimmed = value.trim().toLowerCase();
    if (/^[a-z0-9]{6}$/.test(trimmed)) return trimmed;
  }
  return "";
}

const MISSING_SESSION_PAYLOAD = {
  status: "missing_session",
  message:
    'Missing required parameter \'session_id\'. Ask the user for their 6-character session token shown at https://cgc.codes/explore. Then retry with session_id set to that token.',
  dashboard_url: "https://cgc.codes/explore",
};

/**
 * Builds a tool-specific graceful offline response (HTTP 200).
 *
 * CRITICAL: ChatGPT converts ANY non-2xx status into a ClientResponseError.
 * We must ALWAYS return 200 — even when the browser tunnel is unreachable.
 * The offline payload gives ChatGPT enough context to tell the user what to do.
 */
function offlineResponse(query_type: string) {
  const openUrl = "https://cgc.codes/explore";

  const base = {
    status: "offline",
    message: `Browser tunnel is offline. Open ${openUrl} in a browser tab, keep that tab active (not in the background), wait a few seconds for the tunnel to connect, then retry in ChatGPT.`,
  };

  switch (query_type) {
    case "list_indexed_repositories":
      return { ...base, indexed_repositories: [] };
    case "get_repository_stats":
      return { ...base, total_nodes: 0, total_links: 0, files_count: 0, classes_count: 0, functions_count: 0 };
    case "find_dead_code":
      return { ...base, dead_symbols: [], total_dead_symbols: 0 };
    case "calculate_cyclomatic_complexity":
    case "find_most_complex_functions":
      return { ...base, most_complex_functions: [] };
    case "analyze_code_relationships":
      return { ...base, relationships_count: 0, connected_nodes: [], connected_links: [] };
    case "search_registry_bundles":
      return { ...base, results: [] };
    case "definitions":
    case "callers":
    case "callees":
    case "file_structure":
    case "search":
      return { ...base, nodes: [], links: [] };
    case "cypher":
      return { ...base, nodes: [], links: [] };
    default:
      return { ...base, result: null };
  }
}

export default async function handler(req: any, res: any) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  if (req.method === "OPTIONS") {
    return res.status(200).end();
  }

  try {
    return await handleQuery(req, res);
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Unknown server error";
    console.error("[query] unhandled error:", message);
    return res.status(200).json({
      status: "error",
      error: "Signaling gateway failed to execute tunnel query.",
      details: message,
      message: "Open https://cgc.codes/explore in a browser tab and retry.",
    });
  }
}

async function handleQuery(req: any, res: any) {
  const method = req.method;
  const params = method === "POST" ? (req.body || {}) : (req.query || {});
  const { repo, query_type, target, cypher_query, branch, commit } = params;

  if (!query_type || typeof query_type !== "string") {
    return res.status(400).json({
      error: "Missing required parameter 'query_type'. Expected: 'definitions', 'callers', 'callees', 'file_structure', or 'cypher'."
    });
  }

  const isGlobalTool = query_type === "list_indexed_repositories" || query_type === "search_registry_bundles";

  if (!isGlobalTool) {
    if (!repo || typeof repo !== "string") {
      return res.status(400).json({ error: "Missing required parameter 'repo' (owner/repo)." });
    }
  }

  const supabaseUrl = process.env.VITE_SUPABASE_URL || process.env.SUPABASE_URL;
  const supabaseAnonKey = process.env.VITE_SUPABASE_ANON_KEY || process.env.SUPABASE_ANON_KEY;

  if (!supabaseUrl || !supabaseAnonKey) {
    return res.status(500).json({
      error: "Server configuration error: Supabase credentials are not configured on Vercel."
    });
  }

  const supabase = createClient(supabaseUrl, supabaseAnonKey);

  const wasmQueries = ["definitions", "callers", "callees", "file_structure", "search", "cypher"];
  const isWasmQuery = wasmQueries.includes(query_type);

  const sessionToken = extractSessionToken(params);

  if (!sessionToken) {
    // MUST be 200 — ChatGPT maps non-2xx responses to ClientResponseError and drops the body
    return res.status(200).json({
      ...MISSING_SESSION_PAYLOAD,
      ...offlineResponse(typeof query_type === "string" ? query_type : "unknown"),
    });
  }

  const channelName = `cgc-tunnel-${sessionToken}`;

  const channel = supabase.channel(channelName);
  const requestId = Math.random().toString(36).substring(2, 15);
  let hasResponded = false;

  // Cleanup helper
  const cleanup = () => {
    try { supabase.removeChannel(channel); } catch (err) {}
  };

  try {
    if (isWasmQuery) {
      // ── WASM Query Path (definitions, callers, callees, file_structure, search, cypher) ──
      let wasmResponse: any = null;
      let resolveWait: (() => void) | null = null;
      const waitPromise = new Promise<void>((resolve) => { resolveWait = resolve; });

      channel.on("broadcast", { event: "query-response" }, ({ payload }: { payload: any }) => {
        if (payload && payload.id === requestId) {
          hasResponded = true;
          wasmResponse = payload;
          cleanup();
          if (resolveWait) resolveWait();
        }
      });

      await new Promise<void>((resolve, reject) => {
        channel.subscribe((status: string) => {
          if (status === "SUBSCRIBED") resolve();
          else if (status === "CLOSED" || status === "TIMED_OUT")
            reject(new Error(`Failed to subscribe to tunnel channel: ${status}`));
        });
      });

      // 300ms propagation buffer — balances tab-wake latency vs Vercel's 10s function cap
      await new Promise<void>((resolve) => setTimeout(resolve, 300));

      const sendStatus = await channel.send({
        type: "broadcast",
        event: "query-request",
        payload: {
          id: requestId,
          queryType: query_type,
          target: target || cypher_query || "",
          params: { cypher_query, repo }
        }
      });

      if (sendStatus !== "ok") {
        cleanup();
        // 502 is safe here — it's a network-level failure, not an offline browser
        return res.status(502).json({
          error: "Failed to broadcast query to the signaling tunnel.",
          details: sendStatus
        });
      }

      // 6s cap — background tabs can delay Supabase broadcast delivery; stay under Vercel 10s limit
      const safetyTimeout = setTimeout(() => { if (resolveWait) resolveWait(); }, 6000);
      await waitPromise;
      clearTimeout(safetyTimeout);

      // NEVER return 4xx for offline — ChatGPT maps every non-2xx to ClientResponseError
      if (!hasResponded) {
        return res.status(200).json(offlineResponse(query_type));
      }

      if (wasmResponse?.status === "success") {
        return res.status(200).json(wasmResponse.result ?? offlineResponse(query_type));
      }

      // WASM execution error in the browser — still 200 so ChatGPT reads the error text
      return res.status(200).json({
        status: "error",
        error: "Query execution failed inside client Kuzu WASM database.",
        details: wasmResponse?.error
      });

    } else {
      // ── MCP Tool Path (get_repository_stats, find_dead_code, list_indexed_repositories, etc.) ──
      let toolResponse: any = null;
      let resolveWait: (() => void) | null = null;
      const waitPromise = new Promise<void>((resolve) => { resolveWait = resolve; });

      channel.on("broadcast", { event: "tool-call-response" }, ({ payload }: { payload: any }) => {
        if (payload && payload.id === requestId) {
          hasResponded = true;
          toolResponse = payload;
          cleanup();
          if (resolveWait) resolveWait();
        }
      });

      await new Promise<void>((resolve, reject) => {
        channel.subscribe((status: string) => {
          if (status === "SUBSCRIBED") resolve();
          else if (status === "CLOSED" || status === "TIMED_OUT")
            reject(new Error(`Failed to subscribe to tunnel channel: ${status}`));
        });
      });

      // 300ms propagation buffer — balances tab-wake latency vs Vercel's 10s function cap
      await new Promise<void>((resolve) => setTimeout(resolve, 300));

      const toolArgs = { repo, ...params };

      const sendStatus = await channel.send({
        type: "broadcast",
        event: "tool-call-request",
        payload: { id: requestId, toolName: query_type, args: toolArgs }
      });

      if (sendStatus !== "ok") {
        cleanup();
        return res.status(502).json({
          error: `Failed to broadcast Python tool '${query_type}' to the signaling tunnel.`,
          details: sendStatus
        });
      }

      // 6s cap — background tabs can delay Supabase broadcast delivery; stay under Vercel 10s limit
      const safetyTimeout = setTimeout(() => { if (resolveWait) resolveWait(); }, 6000);
      await waitPromise;
      clearTimeout(safetyTimeout);

      // NEVER return 4xx for offline — ChatGPT maps every non-2xx to ClientResponseError
      if (!hasResponded) {
        return res.status(200).json(offlineResponse(query_type));
      }

      if (toolResponse?.status === "error") {
        // Tool execution failed inside the browser — still 200 so ChatGPT reads the details
        return res.status(200).json({
          status: "error",
          error: `Python MCP execution failed for tool '${query_type}'.`,
          details: toolResponse.error
        });
      }

      // Guard: res.json(undefined) produces `{}` which ChatGPT misreads as ClientResponseError
      const toolResult = toolResponse?.result;
      if (toolResult === undefined || toolResult === null) {
        return res.status(200).json(offlineResponse(query_type));
      }

      return res.status(200).json(toolResult);
    }

  } catch (error: any) {
    cleanup();
    console.error("Signaling tunnel query error:", error);
    // Return 200 even for unexpected errors — ChatGPT must be able to read the error text
    return res.status(200).json({
      status: "error",
      error: "Signaling gateway failed to execute tunnel query.",
      details: error.message,
      message: "Open https://cgc.codes/explore in a browser tab and retry."
    });
  }
}
