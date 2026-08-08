# Manual UX and Functional Checklist

- Launch extension in VS Code Extension Development Host.
- Verify `CGC: Run Indexing Wizard` completes with both modes.
- Open a source file and confirm CodeLens entries appear for declarations.
- Hover over a symbol and confirm complexity and caller count metadata.
- Trigger `CGC: Analyze Relationships` and validate QuickPick navigation to caller file/line.
- Trigger `CGC: Show Call Graph`; click graph item and verify editor jump behavior.
- Move cursor between symbols and confirm webview updates with editor selection sync.
- Save a file after modifying declaration signature and validate impact warning toast.
- Open `Cypher Search` view, run default query, and validate result rendering.
- Validate Repositories/Bundles/Watches lists populate and refresh after indexing.
- Negative paths:
  - Set invalid `cgc.executable` and confirm user-visible failure messages.
  - Run invalid Cypher in view and confirm graceful error response.
  - Test with empty workspace/index and ensure no crashes.
