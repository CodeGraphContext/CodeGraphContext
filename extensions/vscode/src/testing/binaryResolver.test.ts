import test from "node:test";
import assert from "node:assert/strict";
import * as fs from "fs";
import * as os from "os";
import * as path from "path";

import {
  bundledBinaryName,
  bundledBinaryPath,
  defaultDatabaseMode,
  ensureExecutable,
} from "../mcp/binaryResolver";

// Covers the pure helpers only; resolveCgcBinary needs the vscode API.

test("bundledBinaryName matches the build.yml artifact names", () => {
  const name = bundledBinaryName();
  // undefined on unsupported arches; otherwise must be a published name.
  if (name !== undefined) {
    assert.ok(
      ["cgc-windows.exe", "cgc-linux-x86_64", "cgc-macos-arm64"].includes(name),
      `Unexpected bundled binary name: ${name}`
    );
  }
});

test("bundledBinaryPath joins under the extension's bin/ dir", () => {
  const fake = "/tmp/some-ext-root";
  const expected = bundledBinaryName();
  const p = bundledBinaryPath(fake);
  if (expected === undefined) {
    assert.equal(p, undefined);
  } else {
    assert.equal(p, path.join(fake, "bin", expected));
  }
});

test("defaultDatabaseMode is kuzudb on win32 and falkordb elsewhere", () => {
  const expected = process.platform === "win32" ? "kuzudb" : "falkordb";
  assert.equal(defaultDatabaseMode(), expected);
});

test("ensureExecutable flips the +x bit on Unix when missing", { skip: os.platform() === "win32" }, () => {
  const tmp = path.join(os.tmpdir(), `cgc-resolver-test-${process.pid}`);
  fs.writeFileSync(tmp, "#!/bin/sh\necho hi\n", { mode: 0o644 });
  try {
    const before = fs.statSync(tmp).mode & 0o777;
    assert.equal(before & 0o111, 0, "precondition: file should not be executable");

    ensureExecutable(tmp);

    const after = fs.statSync(tmp).mode & 0o777;
    assert.notEqual(after & 0o111, 0, "ensureExecutable should add the +x bit");
  } finally {
    fs.unlinkSync(tmp);
  }
});

test("ensureExecutable is a no-op for files that are already executable", { skip: os.platform() === "win32" }, () => {
  const tmp = path.join(os.tmpdir(), `cgc-resolver-test-${process.pid}-2`);
  fs.writeFileSync(tmp, "#!/bin/sh\necho hi\n", { mode: 0o755 });
  try {
    const before = fs.statSync(tmp).mode & 0o777;
    ensureExecutable(tmp);
    const after = fs.statSync(tmp).mode & 0o777;
    assert.equal(before, after);
  } finally {
    fs.unlinkSync(tmp);
  }
});

test("ensureExecutable swallows errors for missing files", () => {
  // Must not throw; spawn surfaces a clearer error later.
  ensureExecutable(path.join(os.tmpdir(), "definitely-not-here-cgc-xyz"));
});
