// website/src/lib/kuzu-coordinator.ts
import type { RealtimeChannel } from "@supabase/supabase-js";
import { getSupabaseClient } from "./supabase-client";

export type QueryExecutionCallback = (
  queryType: string,
  target: string,
  params: any
) => Promise<any>;

export type ToolsListCallback = () => Promise<any[]>;

export type ToolCallCallback = (toolName: string, args: any) => Promise<any>;

const VISIBILITY_RECONNECT_DEBOUNCE_MS = 2000;

function isChannelJoined(channel: RealtimeChannel | null): boolean {
  return channel?.state === "joined";
}

export class KuzuCoordinator {
  private channelName: string;
  private channel: RealtimeChannel | null = null;

  private executeQueryCallback: QueryExecutionCallback;
  private getToolsCallback: ToolsListCallback;
  private executeToolCallback: ToolCallCallback;

  private isStarted = false;
  private isReconnecting = false;
  private visibilityDebounceTimer: ReturnType<typeof setTimeout> | null = null;
  private keepaliveInterval: ReturnType<typeof setInterval> | null = null;

  constructor(
    _supabaseUrl: string,
    _supabaseAnonKey: string,
    channelName: string,
    executeQueryCallback: QueryExecutionCallback,
    getToolsCallback: ToolsListCallback,
    executeToolCallback: ToolCallCallback
  ) {
    this.channelName = channelName;
    this.executeQueryCallback = executeQueryCallback;
    this.getToolsCallback = getToolsCallback;
    this.executeToolCallback = executeToolCallback;
  }

  private isTunnelHealthy(): boolean {
    return isChannelJoined(this.channel);
  }

  private handleVisibilityChange = () => {
    if (document.visibilityState !== "visible" || !this.isStarted) return;

    if (this.visibilityDebounceTimer) {
      clearTimeout(this.visibilityDebounceTimer);
    }

    this.visibilityDebounceTimer = setTimeout(() => {
      this.visibilityDebounceTimer = null;
      void this.maybeReconnectAfterVisibility();
    }, VISIBILITY_RECONNECT_DEBOUNCE_MS);
  };

  private async maybeReconnectAfterVisibility() {
    if (!this.isStarted || this.isReconnecting) return;
    if (this.isTunnelHealthy()) return;

    console.log(
      "[KuzuCoordinator] Tunnel not joined after tab became visible — reconnecting once..."
    );
    this.isReconnecting = true;
    try {
      await this.stop(true);
      await new Promise((r) => setTimeout(r, 250));
      this.start();
    } finally {
      this.isReconnecting = false;
    }
  }

  /**
   * Subscribes to the real-time signaling channel and listens for queries/MCP events.
   */
  public start() {
    this.isStarted = true;

    if (typeof window !== "undefined" && typeof document !== "undefined") {
      document.removeEventListener("visibilitychange", this.handleVisibilityChange);
      document.addEventListener("visibilitychange", this.handleVisibilityChange);
    }

    if (this.isTunnelHealthy()) return;

    const supabase = getSupabaseClient();

    if (!this.channel) {
      console.log(`[KuzuCoordinator] Subscribing to query channel: ${this.channelName}`);
      this.channel = supabase.channel(this.channelName);
      this.setupChannelListeners(this.channel, this.channelName);
      this.channel.subscribe((status: string) => {
        if (status === "SUBSCRIBED") {
          console.log(
            `[KuzuCoordinator] ✅ Subscribed to query channel: ${this.channelName}`
          );
        }
      });
    }

    // Keep WebSocket warm when ChatGPT tab steals focus (Firefox/Chrome throttle background tabs)
    if (this.keepaliveInterval) clearInterval(this.keepaliveInterval);
    this.keepaliveInterval = setInterval(() => {
      if (!this.isStarted) return;
      try {
        this.channel?.send({
          type: "broadcast",
          event: "tunnel-keepalive",
          payload: { t: Date.now() }
        });
      } catch {
        /* ignore */
      }
    }, 15000);
  }

  private setupChannelListeners(channel: RealtimeChannel, name: string) {
    channel
      .on(
        "broadcast",
        { event: "query-request" },
        async ({ payload }: { payload: any }) => {
          const { id, queryType, target, params } = payload || {};
          if (!id) return;
          console.log(
            `[KuzuCoordinator] 📥 Query request received on [${name}]: id=${id}, type=${queryType}`
          );
          try {
            const result = await this.executeQueryCallback(queryType, target, params);
            await channel.send({
              type: "broadcast",
              event: "query-response",
              payload: { id, status: "success", result },
            });
          } catch (err: any) {
            if (err?.message?.startsWith("SILENT_IGNORE")) {
              console.log(`[KuzuCoordinator] 🔌 Bypassing query: ${err.message}`);
              return;
            }
            await channel.send({
              type: "broadcast",
              event: "query-response",
              payload: { id, status: "error", error: err.message },
            });
          }
        }
      )
      .on(
        "broadcast",
        { event: "tool-call-request" },
        async ({ payload }: { payload: any }) => {
          const { id, toolName, args } = payload || {};
          if (!id || !toolName) return;
          console.log(
            `[KuzuCoordinator] 📥 MCP Tool Call request received on [${name}]: id=${id}, name=${toolName}`
          );
          try {
            const result = await this.executeToolCallback(toolName, args);
            await channel.send({
              type: "broadcast",
              event: "tool-call-response",
              payload: { id, status: "success", result },
            });
          } catch (err: any) {
            if (err?.message?.startsWith("SILENT_IGNORE")) {
              console.log(`[KuzuCoordinator] 🔌 Bypassing tool call: ${err.message}`);
              return;
            }
            await channel.send({
              type: "broadcast",
              event: "tool-call-response",
              payload: { id, status: "error", error: err.message },
            });
          }
        }
      );
  }

  public async stop(keepStarted = false) {
    if (!keepStarted) {
      this.isStarted = false;
      if (typeof window !== "undefined" && typeof document !== "undefined") {
        document.removeEventListener("visibilitychange", this.handleVisibilityChange);
      }
    }

    if (this.visibilityDebounceTimer) {
      clearTimeout(this.visibilityDebounceTimer);
      this.visibilityDebounceTimer = null;
    }

    const supabase = getSupabaseClient();

    if (this.channel) {
      console.log(`[KuzuCoordinator] Unsubscribing from query tunnel: ${this.channelName}`);
      try {
        await supabase.removeChannel(this.channel);
      } catch {
        /* ignore */
      }
      this.channel = null;
    }

    if (this.keepaliveInterval) {
      clearInterval(this.keepaliveInterval);
      this.keepaliveInterval = null;
    }
  }
}
