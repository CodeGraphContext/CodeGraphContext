import { CgcEvent, CgcEventType } from "../types/cgc";

type Listener = (event: CgcEvent) => void;

/**
 * Lightweight pub/sub event bus for CGC extension events.
 * All UI components subscribe here instead of managing their own polling.
 */
export class CgcEventBus {
  private readonly listeners = new Map<CgcEventType, Set<Listener>>();

  public on(type: CgcEventType, listener: Listener): () => void {
    if (!this.listeners.has(type)) {
      this.listeners.set(type, new Set());
    }
    this.listeners.get(type)!.add(listener);
    return () => this.off(type, listener);
  }

  public off(type: CgcEventType, listener: Listener): void {
    this.listeners.get(type)?.delete(listener);
  }

  public emit(type: CgcEventType, payload?: unknown): void {
    const event: CgcEvent = { type, payload };
    for (const listener of this.listeners.get(type) ?? []) {
      try {
        listener(event);
      } catch {
        // individual listener failures must not break the bus
      }
    }
  }

  public dispose(): void {
    this.listeners.clear();
  }
}

/** Singleton event bus shared across the extension. */
export const cgcEvents = new CgcEventBus();
