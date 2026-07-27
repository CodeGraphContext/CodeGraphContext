import test from "node:test";
import assert from "node:assert/strict";
import { extractDeclarationSignature } from "./parser";

test("extracts function signature", () => {
  assert.equal(extractDeclarationSignature("def run_task(arg1, arg2):"), "def run_task(arg1, arg2)");
});

test("extracts class signature", () => {
  assert.equal(extractDeclarationSignature("class Worker(BaseWorker):"), "class Worker(BaseWorker)");
});

test("returns undefined for non declaration", () => {
  assert.equal(extractDeclarationSignature("x = 1"), undefined);
});
