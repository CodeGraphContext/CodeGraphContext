import * as fs from "fs";
import * as os from "os";
import * as path from "path";
import * as vscode from "vscode";

export type BinarySource = "user-override" | "bundled" | "path";

export interface ResolvedBinary {
  command: string;
  extraArgs: string[];
  source: BinarySource;
  bundledPath?: string;
}

// Names must match the artifact names uploaded by .github/workflows/build.yml.
export function bundledBinaryName(): string | undefined {
  switch (process.platform) {
    case "win32":
      return "cgc-windows.exe";
    case "darwin":
      return process.arch === "arm64" ? "cgc-macos-arm64" : undefined;
    case "linux":
      return process.arch === "x64" ? "cgc-linux-x86_64" : undefined;
    default:
      return undefined;
  }
}

export function bundledBinaryPath(extensionPath: string): string | undefined {
  const name = bundledBinaryName();
  if (!name) return undefined;
  return path.join(extensionPath, "bin", name);
}

// Order: user override > bundled binary > `cgc` on PATH.
export function resolveCgcBinary(
  context: vscode.ExtensionContext,
  cfg: vscode.WorkspaceConfiguration
): ResolvedBinary {
  const raw = cfg.get<string>("executable", "cgc").trim();
  const segments = raw.split(/\s+/).filter(Boolean);
  const userValue = segments[0] ?? "cgc";
  const userArgs = segments.slice(1);

  // Plain "cgc" is the default — don't let it shadow the bundled binary.
  const userOverrode = userValue !== "" && userValue !== "cgc";
  if (userOverrode) {
    return { command: userValue, extraArgs: userArgs, source: "user-override" };
  }

  const bundled = bundledBinaryPath(context.extensionPath);
  if (bundled && fs.existsSync(bundled)) {
    return { command: bundled, extraArgs: userArgs, source: "bundled", bundledPath: bundled };
  }

  return { command: userValue || "cgc", extraArgs: userArgs, source: "path" };
}

// Release tarballs strip the +x bit on Linux/macOS, so set it on first use.
export function ensureExecutable(filePath: string): void {
  if (os.platform() === "win32") return;
  try {
    const stat = fs.statSync(filePath);
    if ((stat.mode & 0o111) === 0) {
      fs.chmodSync(filePath, stat.mode | 0o755);
    }
  } catch {
    // spawn will report a better error than we can.
  }
}

// FalkorDB needs redislite, which doesn't build on Windows. KuzuDB is embedded.
export function defaultDatabaseMode(): string {
  return process.platform === "win32" ? "kuzudb" : "falkordb";
}
