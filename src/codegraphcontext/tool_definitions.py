TOOLS = {
    "add_code_to_graph": {
        "name": "add_code_to_graph",
        "description": "Performs a one-time scan of a local folder to add its code to the graph. Ideal for indexing libraries, dependencies, or projects not being actively modified. Returns a job ID for background processing.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the repository root"
                },
                "is_dependency": {
                    "type": "boolean",
                    "description": "Whether this code is a dependency.",
                    "default": False
                }
            },
            "required": ["repo_path"]
        }
    },

    "check_job_status": {
        "name": "check_job_status",
        "description": "Check the status and progress of a background job.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_id": {
                    "type": "string",
                    "description": "Job ID from a previous tool call"
                }
            },
            "required": ["job_id"]
        }
    },

    "list_jobs": {
        "name": "list_jobs",
        "description": "List all background jobs and their current status.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },

    "find_code": {
        "name": "find_code",
        "description": "Find relevant code snippets related to a keyword (e.g., function name, class name, or content).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Keyword or phrase to search for"
                },
                "fuzzy_search": {
                    "type": "boolean",
                    "description": "Whether to use fuzzy search",
                    "default": False
                },
                "edit_distance": {
                    "type": "number",
                    "description": "Edit distance for fuzzy search (between 0-2)",
                    "default": 2
                },
                "repo_path": {
                    "type": "string",
                    "description": "Optional: Path to the repository to restrict the search to."
                }
            },
            "required": ["query"]
        }
    },

    "analyze_code_relationships": {
        "name": "analyze_code_relationships",
        "description": "Analyze code relationships like 'who calls this function' or 'class hierarchy'.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "enum": [
                        "find_callers",
                        "find_callees",
                        "find_all_callers",
                        "find_all_callees",
                        "find_importers",
                        "who_modifies",
                        "class_hierarchy",
                        "overrides",
                        "dead_code",
                        "call_chain",
                        "module_deps",
                        "variable_scope",
                        "find_complexity",
                        "find_functions_by_argument",
                        "find_functions_by_decorator"
                    ]
                },
                "target": {
                    "type": "string",
                    "description": "The function, class, or module to analyze."
                },
                "context": {
                    "type": "string",
                    "description": "Optional file path for precise results."
                },
                "repo_path": {
                    "type": "string",
                    "description": "Optional repository path."
                }
            },
            "required": ["query_type", "target"]
        }
    },

    "watch_directory": {
        "name": "watch_directory",
        "description": "Continuously monitors a directory and keeps graph updated.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to repository root"
                }
            },
            "required": ["repo_path"]
        }
    },

    "execute_cypher_query": {
        "name": "execute_cypher_query",
        "description": "Run a read-only Cypher query against the code graph.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "cypher_query": {
                    "type": "string",
                    "description": "The Cypher query to execute"
                }
            },
            "required": ["cypher_query"]
        }
    },

    "add_package_to_graph": {
        "name": "add_package_to_graph",
        "description": "Add a package to the graph.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "package_name": {
                    "type": "string"
                },
                "language": {
                    "type": "string",
                    "enum": ["python", "javascript", "typescript", "java", "c", "go", "ruby", "php", "cpp"]
                },
                "is_dependency": {
                    "type": "boolean",
                    "default": True
                }
            },
            "required": ["package_name", "language"]
        }
    },

    "find_dead_code": {
        "name": "find_dead_code",
        "description": "Find potentially unused functions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "exclude_decorated_with": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": []
                },
                "repo_path": {
                    "type": "string"
                }
            }
        }
    },

    "calculate_cyclomatic_complexity": {
        "name": "calculate_cyclomatic_complexity",
        "description": "Calculate complexity of a function.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "function_name": {"type": "string"},
                "repo_path": {"type": "string"}
            },
            "required": ["function_name"]
        }
    },

    "find_most_complex_functions": {
        "name": "find_most_complex_functions",
        "description": "Find most complex functions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 10},
                "repo_path": {"type": "string"}
            }
        }
    },

    "list_indexed_repositories": {
        "name": "list_indexed_repositories",
        "description": "List all indexed repositories.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },

    "delete_repository": {
        "name": "delete_repository",
        "description": "Delete a repository from the graph.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "The path of the repository to delete."
                }
            },
            "required": ["repo_path"]
        }
    },

    "visualize_graph_query": {
        "name": "visualize_graph_query",
        "description": "Generate a Neo4j visualization URL for a Cypher query.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "cypher_query": {"type": "string"}
            },
            "required": ["cypher_query"]
        }
    },

    "list_watched_paths": {
        "name": "list_watched_paths",
        "description": "List all watched directories.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },

    "unwatch_directory": {
        "name": "unwatch_directory",
        "description": "Stop watching a directory.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_path": {"type": "string"}
            },
            "required": ["repo_path"]
        }
    },

    "load_bundle": {
        "name": "load_bundle",
        "description": "Load a pre-indexed bundle.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "bundle_name": {"type": "string"},
                "clear_existing": {"type": "boolean", "default": False}
            },
            "required": ["bundle_name"]
        }
    },

    "search_registry_bundles": {
        "name": "search_registry_bundles",
        "description": "Search registry bundles.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "unique_only": {"type": "boolean", "default": False}
            }
        }
    },

    "get_repository_stats": {
        "name": "get_repository_stats",
        "description": "Get repository statistics.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_path": {"type": "string"}
            }
        }
    },

    "discover_codegraph_contexts": {
        "name": "discover_codegraph_contexts",
        "description": "Discover .codegraphcontext folders.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_path": {"type": "string"},
                "max_depth": {"type": "integer", "default": 1}
            }
        }
    },

    "switch_context": {
        "name": "switch_context",
        "description": "Switch active graph context.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "context_path": {"type": "string"},
                "save": {"type": "boolean", "default": True}
            },
            "required": ["context_path"]
        }
    },

    "generate_report": {
        "name": "generate_report",
        "description": "Generate codegraph report.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "output_path": {"type": "string"},
                "include_java": {"type": "boolean", "default": False},
                "god_node_limit": {"type": "integer", "default": 15},
                "complexity_limit": {"type": "integer", "default": 15},
                "cross_module_limit": {"type": "integer", "default": 20}
            }
        }
    },

    "find_java_spring_endpoints": {
        "name": "find_java_spring_endpoints",
        "description": "Find Spring endpoints.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "http_method": {"type": "string"},
                "path_pattern": {"type": "string"},
                "repo_path": {"type": "string"}
            }
        }
    },

    "find_java_spring_beans": {
        "name": "find_java_spring_beans",
        "description": "Find Spring beans.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "stereotype": {
                    "type": "string",
                    "enum": ["CONTROLLER", "REST_CONTROLLER", "SERVICE", "REPOSITORY", "COMPONENT", "CONFIGURATION"]
                },
                "repo_path": {"type": "string"}
            }
        }
    },

    "find_datasource_nodes": {
        "name": "find_datasource_nodes",
        "description": "Query datasource nodes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "kind": {
                    "type": "string",
                    "enum": ["mysql", "cassandra", "redis"]
                },
                "name": {"type": "string"},
                "include_columns": {"type": "boolean"}
            }
        }
    }
}