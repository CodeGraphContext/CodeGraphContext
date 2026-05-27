// website/api/v1/openapi.json.ts
export default async function handler(req: any, res: any) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
  res.setHeader("Content-Type", "application/json");

  if (req.method === "OPTIONS") {
    return res.status(200).end();
  }

  if (req.method !== "GET") {
    res.setHeader("Allow", "GET");
    return res.status(405).json({ error: `Method ${req.method} not allowed` });
  }

  const host = req.headers.host || "codegraphcontext.vercel.app";
  const protocol = req.headers["x-forwarded-proto"] || "https";
  const baseUrl = `${protocol}://${host}`;

  const spec = {
    openapi: "3.1.0",
    info: {
      title: "CodeGraphContext Tunneling API",
      description:
        "Zero-server-compute API that tunnels code-graph queries to the user's browser at https://cgc.codes/explore. " +
        "Every request MUST include session_id: the 6-character token from the user's dashboard tab (shown on the page or in messages like 'session: l968xz'). " +
        "Without session_id the browser tunnel cannot be reached.",
      version: "1.0.0"
    },
    servers: [
      {
        url: baseUrl,
        description: "CodeGraphContext Production Server"
      }
    ],
    paths: {
      "/api/v1/query": {
        get: {
          summary: "Execute Tunneled Code Graph Query",
          description: "Tunnels standard Cypher queries or direct relationships (definitions, callers, callees, search, file structure) directly to Kuzu WASM.",
          operationId: "querySemanticGraph",
          parameters: [
            {
              name: "repo",
              in: "query",
              description: "GitHub repository path in 'owner/repo' format (e.g. 'requests/requests').",
              required: true,
              schema: { type: "string" }
            },
            {
              name: "query_type",
              in: "query",
              description: "The semantic query lookup to perform.",
              required: true,
              schema: {
                type: "string",
                enum: ["definitions", "callers", "callees", "file_structure", "search", "cypher"]
              }
            },
            {
              name: "target",
              in: "query",
              description: "The target class or function name to locate (required for definitions, callers, callees).",
              required: false,
              schema: { type: "string" }
            },
            {
              name: "cypher_query",
              in: "query",
              description: "Full Cypher query string if 'query_type' is 'cypher'.",
              required: false,
              schema: { type: "string" }
            }
          ],
          responses: {
            "200": {
              description: "Query executed successfully",
              content: {
                "application/json": {
                  schema: {
                    type: "object",
                    properties: {},
                    additionalProperties: true
                  }
                }
              }
            }
          }
        }
      },
      "/api/v1/query/find_dead_code": {
        get: {
          summary: "Find Dead Code",
          description: "Natively executes Python dead-code analysis in browser Pyodide. Detects unreferenced classes, functions, and symbols in the project.",
          operationId: "findDeadCode",
          parameters: [
            {
              name: "repo",
              in: "query",
              description: "GitHub repository in 'owner/repo' format (e.g. 'requests/requests').",
              required: true,
              schema: { type: "string" }
            }
          ],
          responses: {
            "200": {
              description: "Dead code analysis completed successfully",
              content: {
                "application/json": {
                  schema: {
                    type: "object",
                    properties: {},
                    additionalProperties: true
                  }
                }
              }
            }
          }
        }
      },
      "/api/v1/query/calculate_cyclomatic_complexity": {
        get: {
          summary: "Calculate Cyclomatic Complexity",
          description: "Runs complexity evaluations in Pyodide on all function bodies inside the repository.",
          operationId: "calculateCyclomaticComplexity",
          parameters: [
            {
              name: "repo",
              in: "query",
              description: "GitHub repository in 'owner/repo' format (e.g. 'requests/requests').",
              required: true,
              schema: { type: "string" }
            }
          ],
          responses: {
            "200": {
              description: "Complexity metrics returned successfully",
              content: {
                "application/json": {
                  schema: {
                    type: "object",
                    properties: {},
                    additionalProperties: true
                  }
                }
              }
            }
          }
        }
      },
      "/api/v1/query/find_most_complex_functions": {
        get: {
          summary: "Find Most Complex Functions",
          description: "Identifies hot spots of complexity in code, listing the functions with the highest complexity scores.",
          operationId: "findMostComplexFunctions",
          parameters: [
            {
              name: "repo",
              in: "query",
              description: "GitHub repository in 'owner/repo' format (e.g. 'requests/requests').",
              required: true,
              schema: { type: "string" }
            },
            {
              name: "limit",
              in: "query",
              description: "Maximum number of functions to return (default is 10).",
              required: false,
              schema: { type: "integer", default: 10 }
            }
          ],
          responses: {
            "200": {
              description: "Most complex functions retrieved successfully",
              content: {
                "application/json": {
                  schema: {
                    type: "object",
                    properties: {},
                    additionalProperties: true
                  }
                }
              }
            }
          }
        }
      },
      "/api/v1/query/analyze_code_relationships": {
        get: {
          summary: "Analyze Code Relationships",
          description: "Examines call coupling, class inheritances, imports, and referencing across symbols in the repository.",
          operationId: "analyzeCodeRelationships",
          parameters: [
            {
              name: "repo",
              in: "query",
              description: "GitHub repository in 'owner/repo' format (e.g. 'requests/requests').",
              required: true,
              schema: { type: "string" }
            },
            {
              name: "symbol",
              in: "query",
              description: "Target symbol name to inspect relationships for.",
              required: true,
              schema: { type: "string" }
            }
          ],
          responses: {
            "200": {
              description: "Relationships analyzed successfully",
              content: {
                "application/json": {
                  schema: {
                    type: "object",
                    properties: {},
                    additionalProperties: true
                  }
                }
              }
            }
          }
        }
      },
      "/api/v1/query/get_repository_stats": {
        get: {
          summary: "Get Repository Stats",
          description: "Retrieves global graph metrics (counts of files, classes, methods, and relationship linkages).",
          operationId: "getRepositoryStats",
          parameters: [
            {
              name: "repo",
              in: "query",
              description: "GitHub repository in 'owner/repo' format (e.g. 'requests/requests').",
              required: true,
              schema: { type: "string" }
            }
          ],
          responses: {
            "200": {
              description: "Stats retrieved successfully",
              content: {
                "application/json": {
                  schema: {
                    type: "object",
                    properties: {},
                    additionalProperties: true
                  }
                }
              }
            }
          }
        }
      },


      "/api/v1/query/generate_report": {
        get: {
          summary: "Generate Code Intelligence Report",
          description: "Compiles a comprehensive, formatted code analytics report.",
          operationId: "generateReport",
          parameters: [
            {
              name: "repo",
              in: "query",
              required: true,
              schema: { type: "string" }
            }
          ],
          responses: {
            "200": {
              description: "Report compiled successfully"
            }
          }
        }
      },

      "/api/v1/query/list_indexed_repositories": {
        get: {
          summary: "List Indexed Repositories",
          description:
            "Returns all repository graphs indexed in the user's browser (IndexedDB). Requires session_id from their open https://cgc.codes/explore tab.",
          operationId: "listIndexedRepositories",
          parameters: [
            {
              name: "repo",
              in: "query",
              description: "Optional GitHub repository path to isolate results.",
              required: false,
              schema: { type: "string" }
            }
          ],
          responses: {
            "200": {
              description: "Indexed repository list returned successfully",
              content: {
                "application/json": {
                  schema: {
                    type: "object",
                    properties: {},
                    additionalProperties: true
                  }
                }
              }
            }
          }
        }
      }
    }
  };

  // Programmatically inject 'branch' and 'commit' parameters to all endpoints in a highly DRY, robust manner!
  const commonParams = [
    {
      name: "session_id",
      in: "query",
      description:
        "REQUIRED on every call. 6-character session token from the user's open https://cgc.codes/explore browser tab. " +
        "Always extract from the conversation (e.g. user says 'session: l968xz' → session_id=l968xz). Never omit this parameter.",
      required: true,
      schema: { type: "string", minLength: 6, maxLength: 6, pattern: "^[a-z0-9]{6}$" }
    },
    {
      name: "branch",
      in: "query",
      description: "Optional active branch name of the repository (e.g. 'main') for routing isolation.",
      required: false,
      schema: { type: "string" }
    },
    {
      name: "commit",
      in: "query",
      description: "Optional active 7-character commit hash of the repository (e.g. 'a1b2c3d') for routing isolation.",
      required: false,
      schema: { type: "string" }
    }
  ];

  for (const pathKey of Object.keys(spec.paths)) {
    const pathObj = (spec.paths as any)[pathKey];
    for (const method of ["get", "post"]) {
      if (pathObj[method] && Array.isArray(pathObj[method].parameters)) {
        const hasSession = pathObj[method].parameters.some((p: any) => p.name === "session_id");
        if (!hasSession) {
          pathObj[method].parameters.push(...commonParams);
        }
      }
    }
  }

  return res.status(200).json(spec);
}
