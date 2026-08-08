import test from "node:test";
import assert from "node:assert/strict";
import { renderSetupHtml } from "../webview/setupTemplate";

test("setup panel renders all config controls", () => {
  const html = renderSetupHtml("cgc", "falkordb", "/usr/bin/uvx", 1200, "bolt://localhost:7687");
  assert.ok(html.includes("id=\"executable\""));
  assert.ok(html.includes("id=\"dbMode\""));
  assert.ok(html.includes("id=\"pythonPackagePath\""));
  assert.ok(html.includes("id=\"maxToolResponseTokens\""));
  assert.ok(html.includes("id=\"neo4jUri\""));
  assert.ok(html.includes("Test Connection"));
  assert.ok(html.includes("Save & Apply"));
});
