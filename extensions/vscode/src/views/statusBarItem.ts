import * as vscode from "vscode";
import { CgcMcpClient } from "../mcp/client";
import { cgcEvents } from "../mcp/eventBus";

type StatusState = "online" | "offline" | "indexing";

/**
 * Persistent status bar item showing CGC health.
 *
 *  Green  = indexed + MCP online
 *  Yellow = MCP online but not yet indexed
 *  Red    = MCP offline
 *  Spin   = indexing in progress
 */
export class CgcStatusBarItem implements vscode.Disposable {
  private readonly item: vscode.StatusBarItem;
  private state: StatusState = "offline";
  private indexingCount = 0;
  private spinFrame = 0;
  private spinTimer?: NodeJS.Timeout;

  constructor(private readonly client: CgcMcpClient) {
    this.item = vscode.window.createStatusBarItem(
      vscode.StatusBarAlignment.Right,
      1000
    );
    this.item.command = "cgc.openDashboard";
    this.item.tooltip = "CodeGraphContext — click to open dashboard";
    this._subscribeEvents();
    this._render();
    this.item.show();
  }

  private _subscribeEvents(): void {
    cgcEvents.on("mcp:online", () => {
      this.state = "online";
      this._render();
    });
    cgcEvents.on("mcp:offline", () => {
      this.state = "offline";
      this._render();
    });
    cgcEvents.on("index:started", () => {
      this.indexingCount++;
      if (this.state !== "indexing") {
        this.state = "indexing";
        this._startSpin();
      }
    });
    cgcEvents.on("index:done", () => {
      this.indexingCount = Math.max(0, this.indexingCount - 1);
      if (this.indexingCount === 0) {
        this.state = "online";
        this._stopSpin();
        this._render();
      }
    });
    cgcEvents.on("index:failed", () => {
      this.indexingCount = Math.max(0, this.indexingCount - 1);
      if (this.indexingCount === 0) {
        this.state = "online";
        this._stopSpin();
        this._render();
      }
    });
    cgcEvents.on("index:progress", (ev: import("../types/cgc").CgcEvent) => {
      const payload = ev.payload as { pct?: number; message?: string } | undefined;
      const pct = payload?.pct;
      const msg = payload?.message ?? "";
      if (typeof pct === "number" && pct > 0) {
        this.item.text = `$(sync~spin) CGC ${pct}%`;
      } else if (msg) {
        this.item.text = `$(sync~spin) CGC — ${msg.slice(0, 30)}`;
      }
    });
  }

  private _startSpin(): void {
    this._stopSpin();
    const frames = ["$(sync~spin)", "$(loading~spin)"];
    this.spinTimer = setInterval(() => {
      this.spinFrame = (this.spinFrame + 1) % frames.length;
      this.item.text = `${frames[this.spinFrame]} CGC — Indexing…`;
    }, 500);
    this.item.text = "$(sync~spin) CGC — Indexing…";
  }

  private _stopSpin(): void {
    if (this.spinTimer) {
      clearInterval(this.spinTimer);
      this.spinTimer = undefined;
    }
  }

  private _render(): void {
    switch (this.state) {
      case "online":
        this.item.text = "$(circle-filled) CGC";
        this.item.color = new vscode.ThemeColor("charts.green");
        this.item.backgroundColor = undefined;
        break;
      case "offline":
        this.item.text = "$(circle-slash) CGC";
        this.item.color = new vscode.ThemeColor("charts.red");
        this.item.backgroundColor = new vscode.ThemeColor(
          "statusBarItem.errorBackground"
        );
        break;
      case "indexing":
        // handled by _startSpin
        break;
    }
  }

  /** Called by extension.ts after MCP start succeeds. */
  public notifyOnline(): void {
    cgcEvents.emit("mcp:online");
  }

  /** Called by extension.ts if MCP start fails or process dies. */
  public notifyOffline(): void {
    cgcEvents.emit("mcp:offline");
  }

  public dispose(): void {
    this._stopSpin();
    this.item.dispose();
  }
}
