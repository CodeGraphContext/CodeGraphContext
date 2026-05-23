import * as fs from "fs";
import * as os from "os";
import * as path from "path";
import * as vscode from "vscode";

/**
 * Where the `cgc` binary came from. Useful for log output and for nudging the
 * user if they're stuck on the system-PATH fallback when a bundled binary
 * should have been available.
 */
export type BinarySource = "user-override" | "bundled" | "path";

export interface ResolvedBinary {
  /** Argv[0] passed to spawn(). */
  command: string;
  /** Extra args parsed out of the user's `cgc.executable` setting (if any). */
  extraArgs: string[];
  source: BinarySource;
  /** Filled in when source === "bundled" so we can chmod +x it on first use. */
  bundledPath?: string;
}

/**
 * Pick the right filename for the PyInstaller artifact on this OS+arch.
 * Names match what `.github/workflows/build.yml` uploads to the release page.
 *
 * Linux arm64 isn't built today — callers will fall back to PATH there.
 */
export function bundledBinaryName(): string | undefined {
  switch (process.platform) {
    case "win32":
      return "cgc-windows.exe";
    case "darwin":
      // Only an arm64 binary is published right now; Intel macs hit the PATH
      // fallback below until/unless we add an x86_64 artifact.
      return process.arch === "arm64" ? "cgc-macos-arm64" : undefined;
    case "linux":
      return process.arch === "x64" ? "cgc-linux-x86_64" : undefined;
    default:
      return undefined;
  }
}

/** Absolute path the fetch script writes the bundled binary to. */
export function bundledBinaryPath(extensionPath: string): string | undefined {
  const name = bundledBinaryName();
  if (!name) return undefined;
  return path.join(extensionPath, "bin", name);
}

/**
 * Resolution order:
 *   1. `cgc.executable` setting, but only if the user has actually changed it
 *      away from the default "cgc". An untouched default shouldn't shadow the
 *      bundled binary — that's the whole point of bundling.
 *   2. The bundled PyInstaller binary at <extensionPath>/bin/<artifact>.
 *   3. Plain `cgc` from PATH (legacy behavior, kept so devs with a local pip
 *      install still work).
 */
export function resolveCgcBinary(
  context: vscode.ExtensionContext,
  cfg: vscode.WorkspaceConfiguration
): ResolvedBinary {
  const raw = cfg.get<string>("executable", "cgc").trim();
  const segments = raw.split(/\s+/).filter(Boolean);
  const userValue = segments[0] ?? "cgc";
  const userArgs = segments.slice(1);

  // Treat the literal default "cgc" as "no override". Anything else (absolute
  // path, `uvx ...`, `python -m cgc`) wins outright.
  const userOverrode = userValue !== "" && userValue !== "cgc";
  if (userOverrode) {
    return { command: userValue, extraArgs: userArgs, source: "user-override" };
  }

  const bundled = bundledBinaryPath(context.extensionPath);
  if (bundled && fs.existsSync(bundled)) {
    return {
      command: bundled,
      extraArgs: userArgs,
      source: "bundled",
      bundledPath: bundled,
    };
  }

  return { command: userValue || "cgc", extraArgs: userArgs, source: "path" };
}

/**
 * PyInstaller artifacts are uploaded without the +x bit on Linux/macOS (the
 * GitHub release tarball strips it). We add it back the first time we spawn,
 * since chmod is cheap and idempotent.
 */
export function ensureExecutable(filePath: string): void {
  if (os.platform() === "win32") return;
  try {
    const stat = fs.statSync(filePath);
    // 0o111 == owner/group/other execute bits.
    if ((stat.mode & 0o111) === 0) {
      fs.chmodSync(filePath, stat.mode | 0o755);
    }
  } catch {
    // The spawn call below will surface a clearer error than we could here.
  }
}

/**
 * Default DB backend per platform. We only consult this when the user hasn't
 * explicitly picked one. FalkorDB depends on redislite, which doesn't build
 * cleanly on Windows; KuzuDB is embedded and works everywhere, so it's the
 * sane Windows default.
 */
export function defaultDatabaseMode(): string {
  return process.platform === "win32" ? "kuzudb" : "falkordb";
}
