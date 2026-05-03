import test from "node:test";
import assert from "node:assert/strict";
import { renderDashboardHtml } from "../webview/dashboardTemplate";

test("dashboard renders key UI elements", () => {
  const html = renderDashboardHtml({
    repos: [{ repo_name: "RepoA", path: "/tmp/repo-a" }],
    hotspots: [{ function_name: "heavyFn", cyclomatic_complexity: 15, path: "/tmp/repo-a/a.ts" }],
    selectedRepo: "/tmp/repo-a"
  });
  assert.ok(html.includes("CodeGraphContext Command Center"));
  assert.ok(html.includes("id=\"repoSelect\""));
  assert.ok(html.includes("Graph Search"));
  assert.ok(html.includes("Risk Map"));
  assert.ok(html.includes("Cypher Quick Console"));
});
