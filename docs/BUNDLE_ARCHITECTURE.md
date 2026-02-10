# CGC Bundle System Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    CGC Bundle Ecosystem                          │
└─────────────────────────────────────────────────────────────────┘

┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│   Source     │         │   Bundle     │         │    User      │
│  Repository  │────────▶│   Creation   │────────▶│  Database    │
│              │         │              │         │              │
└──────────────┘         └──────────────┘         └──────────────┘
      │                         │                         │
      │                         │                         │
      ▼                         ▼                         ▼
  
  git clone              cgc export              cgc load
  cgc index              .cgc file               instant!


## Export Flow

┌─────────────┐
│ Indexed     │
│ Repository  │
└──────┬──────┘
       │
       │ cgc export
       │
       ▼
┌─────────────────────────────────────────┐
│     CGCBundle.export_to_bundle()        │
├─────────────────────────────────────────┤
│ 1. Extract metadata (repo, commit, etc)│
│ 2. Query graph schema                  │
│ 3. Export nodes → nodes.jsonl          │
│ 4. Export edges → edges.jsonl          │
│ 5. Generate stats → stats.json         │
│ 6. Create README.md                    │
│ 7. Package as ZIP                      │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────┐
│  .cgc file  │
│  (ZIP)      │
├─────────────┤
│ metadata    │
│ schema      │
│ nodes       │
│ edges       │
│ stats       │
│ README      │
└─────────────┘


## Import Flow

┌─────────────┐
│  .cgc file  │
└──────┬──────┘
       │
       │ cgc load
       │
       ▼
┌─────────────────────────────────────────┐
│    CGCBundle.import_from_bundle()       │
├─────────────────────────────────────────┤
│ 1. Extract ZIP to temp directory       │
│ 2. Validate bundle structure           │
│ 3. Load metadata.json                  │
│ 4. Create schema (constraints/indexes) │
│ 5. Import nodes (batch processing)     │
│ 6. Build ID mapping (old → new)        │
│ 7. Import edges using ID mapping       │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────┐
│   Graph     │
│  Database   │
│  (Neo4j/    │
│  FalkorDB)  │
└─────────────┘


## Distribution Flow

┌──────────────────────────────────────────────────────────────┐
│              Automated Weekly Releases                        │
│                (GitHub Actions)                               │
└──────────────────────────────────────────────────────────────┘

    ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐
    │  numpy  │  │ pandas  │  │ fastapi │  │ requests│
    └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘
         │            │            │            │
         └────────────┴────────────┴────────────┘
                      │
                      ▼
         ┌────────────────────────┐
         │  Matrix Build Strategy │
         │  (Parallel Processing) │
         └────────┬───────────────┘
                  │
         ┌────────┴────────┐
         │                 │
         ▼                 ▼
    Clone Repo        Index Code
         │                 │
         └────────┬────────┘
                  │
                  ▼
            Export Bundle
                  │
                  ▼
         ┌────────────────┐
         │ GitHub Release │
         │ bundles-DATE   │
         ├────────────────┤
         │ numpy.cgc      │
         │ pandas.cgc     │
         │ fastapi.cgc    │
         │ requests.cgc   │
         │ flask.cgc      │
         └────────────────┘
                  │
                  ▼
         ┌────────────────┐
         │  Users Download│
         │  cgc load      │
         └────────────────┘


## Bundle File Structure

.cgc (ZIP Archive)
│
├── metadata.json
│   ├── cgc_version: "0.1.0"
│   ├── exported_at: "2026-01-13T..."
│   ├── repo: "numpy/numpy"
│   ├── commit: "a1b2c3d4"
│   ├── languages: ["python", "c"]
│   └── format_version: "1.0"
│
├── schema.json
│   ├── node_labels: ["Function", "Class", ...]
│   ├── relationship_types: ["CALLS", "INHERITS", ...]
│   ├── constraints: [...]
│   └── indexes: [...]
│
├── nodes.jsonl (streaming format)
│   {"_id": "4:abc", "_labels": ["Function"], "name": "array", ...}
│   {"_id": "4:def", "_labels": ["Class"], "name": "ndarray", ...}
│   ...
│
├── edges.jsonl (streaming format)
│   {"from": "4:abc", "to": "4:def", "type": "CALLS", ...}
│   {"from": "4:xyz", "to": "4:def", "type": "INHERITS", ...}
│   ...
│
├── stats.json
│   ├── total_nodes: 15234
│   ├── total_edges: 42156
│   ├── files: 1342
│   ├── nodes_by_type: {...}
│   └── edges_by_type: {...}
│
└── README.md
    └── Human-readable description


## CLI Command Flow

User Commands:
┌─────────────────────────────────────────────────────────────┐
│                                                              │
│  cgc export <output> --repo <path>                         │
│       │                                                      │
│       └──▶ bundle_export() ──▶ CGCBundle.export_to_bundle()│
│                                                              │
│  cgc load <bundle>                                          │
│       │                                                      │
│       └──▶ bundle_load() ──▶ CGCBundle.import_from_bundle()│
│                                                              │
│  cgc bundle import <bundle> --clear                         │
│       │                                                      │
│       └──▶ bundle_import() ──▶ CGCBundle.import_from_bundle│
│                                                              │
└─────────────────────────────────────────────────────────────┘


## Use Case: AI Assistant Integration

┌──────────────┐
│ AI Assistant │
│ (Claude/GPT) │
└──────┬───────┘
       │
       │ "Analyze numpy's linalg module"
       │
       ▼
┌──────────────┐
│     MCP      │
│   Server     │
└──────┬───────┘
       │
       │ Query: MATCH (m:Module {name: 'linalg'})...
       │
       ▼
┌──────────────┐
│   Graph DB   │
│  (Pre-loaded │
│  from bundle)│
└──────┬───────┘
       │
       │ Results: Functions, Classes, Dependencies
       │
       ▼
┌──────────────┐
│ AI Assistant │
│  Response    │
└──────────────┘

Time saved: 5-10 minutes of indexing → 10 seconds of loading!


## Comparison: Before vs After

BEFORE (Traditional Indexing):
┌─────────┐    ┌─────────┐    ┌─────────┐
│ User A  │    │ User B  │    │ User C  │
└────┬────┘    └────┬────┘    └────┬────┘
     │              │              │
     ▼              ▼              ▼
  Index numpy   Index numpy   Index numpy
  (10 mins)     (10 mins)     (10 mins)
     │              │              │
     ▼              ▼              ▼
  Database      Database      Database

Total time: 30 minutes
Total storage: 3x redundant


AFTER (Bundle System):
┌─────────┐
│  CI/CD  │
└────┬────┘
     │
     ▼
  Index numpy (once)
  (10 mins)
     │
     ▼
  Export bundle
     │
     ▼
┌─────────────┐
│ numpy.cgc   │
│ (Shared)    │
└─────┬───────┘
      │
      ├──────────┬──────────┐
      │          │          │
      ▼          ▼          ▼
  ┌────────┐ ┌────────┐ ┌────────┐
  │ User A │ │ User B │ │ User C │
  │ (10s)  │ │ (10s)  │ │ (10s)  │
  └────────┘ └────────┘ └────────┘

Total time: 10 mins + 30 seconds
Total storage: 1x + 3x small bundles
Speedup: 60x faster for users!
