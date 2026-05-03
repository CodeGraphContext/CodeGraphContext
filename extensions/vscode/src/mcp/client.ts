import { ChildProcessWithoutNullStreams, spawn } from "child_process";
import * as path from "path";
import * as vscode from "vscode";
import { CgcMcpToolResponse, CgcTool } from "../types/cgc";

interface JsonRpcResponse {
  id?: number;
  result?: unknown;
  error?: { message?: string; data?: unknown };
}

type PendingRequest = {
  resolve: (value: unknown) => void;
  reject: (reason?: unknown) => void;
};

export class CgcMcpClient {
  private proc?: ChildProcessWithoutNullStreams;
  private nextId = 1;
  private pending = new Map<number, PendingRequest>();
  private readonly output = vscode.window.createOutputChannel("CodeGraphContext");

  constructor(private readonly context: vscode.ExtensionContext) {}

  public async ensureStarted(): Promise<void> {
    if (this.proc && !this.proc.killed && this.proc.exitCode === null) {
      return;
    }

    const cfg = vscode.workspace.getConfiguration("cgc");
    const executableSetting = cfg.get<string>("executable", "cgc").trim();
    const pythonPackagePath = cfg.get<string>("pythonPackagePath", "").trim();
    const segments = executableSetting.split(" ").filter(Boolean);
    const executable = segments[0] || "cgc";
    const extraArgs = segments.slice(1);
    const cwd = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    const env: NodeJS.ProcessEnv = { ...process.env, CGC_RUNTIME_DB_TYPE: cfg.get<string>("databaseMode", "falkordb") };
    
    if (pythonPackagePath) {
      env.PYTHONPATH = pythonPackagePath;
    }
    const maxTokens = cfg.get<number>("maxToolResponseTokens", 0);
    if (maxTokens > 0) {
      env.MAX_TOOL_RESPONSE_TOKENS = String(maxTokens);
    }

    try {
      this.output.appendLine(`Spawning CGC: ${executable} ${extraArgs.join(" ")}`);
      const proc = spawn(executable, [...extraArgs, "mcp", "start"], { cwd, env });
      this.proc = proc;
      
      proc.on("error", (err) => {
        this.output.appendLine(`Failed to spawn CGC process: ${err.message}`);
        this.proc = undefined;
      });

      proc.stderr.on("data", (buf) => this.output.appendLine(buf.toString()));
      proc.stdout.on("data", (buf) => this.onStdout(buf.toString()));
      proc.on("exit", (code) => {
        this.output.appendLine(`CGC MCP process exited with code ${code}`);
        for (const [, req] of this.pending) {
          req.reject(new Error("CGC MCP process exited"));
        }
        this.pending.clear();
        this.proc = undefined;
      });

      // Give it a moment to start or fail
      await new Promise((resolve) => setTimeout(resolve, 500));
      
      if (!proc || !proc.stdin) {
        throw new Error("Failed to initialize CGC MCP process (no stdin). Is 'cgc' installed?");
      }

      // Handshake - Use internal methods to avoid infinite recursion through ensureProcessReady()
      await this.internalRequest(proc, "initialize", {
        protocolVersion: "2025-03-26",
        clientInfo: { name: "CodeGraphContext VS Code", version: this.context.extension.packageJSON.version },
        capabilities: {}
      });
      this.internalNotify(proc, "notifications/initialized", {});
      
      this.output.appendLine("CGC MCP handshake successful.");
    } catch (err) {
      this.proc = undefined;
      this.output.appendLine(`CGC Startup Error: ${String(err)}`);
      throw err;
    }
  }

  public async listTools(): Promise<CgcTool[]> {
    const result = await this.request("tools/list", {});
    const tools = (result as { tools?: CgcTool[] }).tools;
    return tools ?? [];
  }

  public async callTool<T>(name: string, args: Record<string, unknown>): Promise<T> {
    const result = (await this.request("tools/call", { name, arguments: args })) as CgcMcpToolResponse;
    const text = result.content?.find((c) => c.type === "text")?.text;
    if (!text) {
      throw new Error(`No text payload returned for tool ${name}`);
    }
    return JSON.parse(text) as T;
  }

  public dispose(): void {
    this.proc?.kill();
    this.output.dispose();
  }

  private onStdout(raw: string): void {
    const lines = raw.split("\n").map((x) => x.trim()).filter(Boolean);
    for (const line of lines) {
      if (!line.startsWith("{")) {
        continue;
      }
      try {
        const msg = JSON.parse(line) as JsonRpcResponse;
        if (typeof msg.id === "number" && this.pending.has(msg.id)) {
          const req = this.pending.get(msg.id)!;
          this.pending.delete(msg.id);
          if (msg.error) {
            const detail = typeof msg.error.data === "string" ? msg.error.data : JSON.stringify(msg.error.data ?? {});
            req.reject(new Error(`${msg.error.message ?? "MCP error"}: ${detail}`));
          } else {
            req.resolve(msg.result);
          }
        }
      } catch (err) {
        this.output.appendLine(`Failed to parse MCP message: ${String(err)}`);
      }
    }
  }

  private async request(method: string, params: Record<string, unknown>): Promise<unknown> {
    for (let attempt = 0; attempt < 2; attempt++) {
      await this.ensureProcessReady();
      if (!this.proc) throw new Error("Process missing");
      try {
        return await this.internalRequest(this.proc, method, params);
      } catch (err) {
        const msg = String(err);
        const isChannelError = msg.includes("Channel has been closed") ||
          msg.includes("stdin is not writable") ||
          msg.includes("process exited");
        if (isChannelError && attempt === 0) {
          this.output.appendLine(`MCP channel error, restarting (${msg})`);
          this.proc?.kill();
          this.proc = undefined;
          await this.ensureStarted();
          continue;
        }
        throw err;
      }
    }
    throw new Error("MCP request failed after retry");
  }

  private notify(method: string, params: Record<string, unknown>): void {
    if (!this.proc) return;
    this.internalNotify(this.proc, method, params);
  }

  private internalRequest(proc: ChildProcessWithoutNullStreams, method: string, params: Record<string, unknown>): Promise<unknown> {
    const id = this.nextId++;
    const payload = JSON.stringify({ jsonrpc: "2.0", id, method, params });
    return new Promise<unknown>((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      if (!proc.stdin.writable) {
        this.pending.delete(id);
        reject(new Error("CGC MCP stdin is not writable"));
        return;
      }
      try {
        proc.stdin.write(`${payload}\n`);
      } catch (err) {
        this.pending.delete(id);
        reject(err);
        return;
      }
      setTimeout(() => {
        if (this.pending.has(id)) {
          this.pending.delete(id);
          reject(new Error(`MCP request timeout (${method})`));
        }
      }, 30_000);
    });
  }

  private internalNotify(proc: ChildProcessWithoutNullStreams, method: string, params: Record<string, unknown>): void {
    if (proc.stdin.writable) {
      proc.stdin.write(`${JSON.stringify({ jsonrpc: "2.0", method, params })}\n`);
    }
  }

  private async ensureProcessReady(): Promise<void> {
    if (!this.proc || this.proc.killed || this.proc.exitCode !== null) {
      await this.ensureStarted();
    }
    
    if (!this.proc || !this.proc.stdin) {
      const cwd = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath ?? "<workspace>";
      throw new Error(`CGC process not ready for workspace ${path.basename(cwd)}. Please check CGC output channel.`);
    }
  }
}
