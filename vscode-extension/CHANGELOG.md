# Change Log

All notable changes to the "CodeGraphContext" extension will be documented in this file.

## [0.1.0] - 2026-02-04

### Added
- Initial release of CodeGraphContext VS Code Extension
- Complete integration with cgc CLI
- Tree view providers:
  - Projects explorer
  - Functions browser
  - Classes browser
  - Call graph viewer
  - Dependencies tracker
- Interactive graph visualization using D3.js
  - Force-directed layout
  - Zoom and pan controls
  - Drag-to-reposition nodes
  - Hover tooltips
- Code lens provider:
  - Inline caller/callee counts
  - Quick access to call graph
  - One-click navigation
- Diagnostics provider:
  - Dead code warnings
  - Complexity warnings
  - Integration with Problems panel
- Command palette integration:
  - Indexing commands
  - Search and navigation
  - Analysis tools
  - Settings access
- Configuration options:
  - Database path
  - Auto-indexing
  - Code lens toggle
  - Diagnostics toggle
  - Complexity threshold
- Bundle loading support
- Status bar integration
- Context menu integration
- Keyboard shortcuts support

### Features
- Real-time file watching and auto-indexing
- Multi-workspace support
- Comprehensive error handling
- Performance optimizations for large codebases

## [Unreleased]

### Planned
- Language Server Protocol (LSP) integration
- Advanced graph filtering options
- Export graph visualizations as images
- Custom Cypher query builder UI
- Integration with Git for change analysis
- Collaborative features
- Performance profiling integration
