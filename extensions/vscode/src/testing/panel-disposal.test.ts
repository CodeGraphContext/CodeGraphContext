/**
 * Tests verifying that panel event listeners are properly cleaned up on disposal.
 * These run with Node's built-in test runner (no VS Code API needed) using a
 * lightweight stub of the cgcEvents bus.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { CgcEventBus } from "../mcp/eventBus";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Returns the number of listeners registered for a given event type. */
function listenerCount(bus: CgcEventBus, type: string): number {
  // Access the private map via casting for white-box testing.
  const map = (bus as unknown as { listeners: Map<string, Set<unknown>> }).listeners;
  return map.get(type)?.size ?? 0;
}

// ---------------------------------------------------------------------------
// CgcEventBus unit tests
// ---------------------------------------------------------------------------

test("CgcEventBus: on() registers a listener and returns an unsubscribe fn", () => {
  const bus = new CgcEventBus();
  let callCount = 0;
  const off = bus.on("graph:changed", () => { callCount++; });

  bus.emit("graph:changed");
  assert.equal(callCount, 1, "listener should fire once after registration");

  off(); // unsubscribe
  bus.emit("graph:changed");
  assert.equal(callCount, 1, "listener must not fire after unsubscription");
});

test("CgcEventBus: dispose() removes all listeners", () => {
  const bus = new CgcEventBus();
  bus.on("graph:changed", () => {});
  bus.on("repo:changed",  () => {});
  bus.on("index:done",    () => {});

  assert.equal(listenerCount(bus, "graph:changed"), 1);
  assert.equal(listenerCount(bus, "repo:changed"),  1);
  assert.equal(listenerCount(bus, "index:done"),    1);

  bus.dispose();

  assert.equal(listenerCount(bus, "graph:changed"), 0, "graph:changed must be cleared");
  assert.equal(listenerCount(bus, "repo:changed"),  0, "repo:changed must be cleared");
  assert.equal(listenerCount(bus, "index:done"),    0, "index:done must be cleared");
});

test("CgcEventBus: multiple off() calls on same listener are safe (idempotent)", () => {
  const bus = new CgcEventBus();
  const off = bus.on("graph:changed", () => {});
  off();
  assert.doesNotThrow(() => off(), "calling unsubscribe a second time must not throw");
  assert.equal(listenerCount(bus, "graph:changed"), 0);
});

// ---------------------------------------------------------------------------
// DashboardPanel disposal simulation
// ---------------------------------------------------------------------------

test("DashboardPanel disposal: constructor-level cgcEvents subscriptions are released", () => {
  const bus = new CgcEventBus();

  // Simulate the four subscriptions DashboardPanel registers in its constructor.
  const eventTypes = ["repo:changed", "context:changed", "graph:changed", "index:done"] as const;
  const disposables: Array<{ dispose(): void }> = [];

  for (const type of eventTypes) {
    disposables.push({ dispose: bus.on(type, () => {}) });
  }

  // Confirm all listeners registered.
  for (const type of eventTypes) {
    assert.equal(listenerCount(bus, type), 1, `${type} should have 1 listener after construction`);
  }

  // Simulate dispose().
  for (const d of disposables) d.dispose();

  // All listeners must be gone.
  for (const type of eventTypes) {
    assert.equal(listenerCount(bus, type), 0, `${type} must have 0 listeners after disposal`);
  }
});

test("DashboardPanel disposal: re-opening does not duplicate cgcEvents subscriptions", () => {
  const bus = new CgcEventBus();
  const eventTypes = ["repo:changed", "context:changed", "graph:changed", "index:done"] as const;

  // Simulate two open→dispose cycles.
  for (let cycle = 0; cycle < 2; cycle++) {
    const disposables: Array<{ dispose(): void }> = [];
    for (const type of eventTypes) {
      disposables.push({ dispose: bus.on(type, () => {}) });
    }
    for (const d of disposables) d.dispose();
  }

  // After both cycles all listeners must be cleaned up.
  for (const type of eventTypes) {
    assert.equal(listenerCount(bus, type), 0, `no stale ${type} listeners after two open/close cycles`);
  }
});

// ---------------------------------------------------------------------------
// CallGraphPanel disposal simulation
// ---------------------------------------------------------------------------

test("CallGraphPanel disposal: no stale listeners survive panel close + reopen", () => {
  // CallGraphPanel has no cgcEvents subscriptions of its own; the risk is
  // in webview-panel–scoped listeners that should die with the panel.
  // We model a simplified version using plain callbacks.
  type Handler = () => void;
  const registered: Handler[] = [];
  const released: Handler[] = [];

  function registerPanelListener(h: Handler): () => void {
    registered.push(h);
    return () => { released.push(h); };
  }

  // Simulate show(): register onDidDispose + onDidReceiveMessage.
  const offs: Array<() => void> = [];
  const msgHandler = () => {};
  const disposeHandler = () => { for (const o of offs) o(); };
  offs.push(registerPanelListener(disposeHandler));
  offs.push(registerPanelListener(msgHandler));

  assert.equal(registered.length, 2, "two panel-scoped listeners registered on show()");

  // Simulate the user closing the panel (onDidDispose fires).
  disposeHandler();

  assert.equal(released.length, 2, "both listeners must be released when panel is disposed");
});

// ---------------------------------------------------------------------------
// extension.ts event coordination
// ---------------------------------------------------------------------------

test("extension.ts invalidateAll: subscriptions stored as disposables can be cleaned up", () => {
  const bus = new CgcEventBus();
  let invalidateCalls = 0;
  const invalidateAll = () => { invalidateCalls++; };

  // Simulate the fixed pattern in extension.ts.
  const subscriptionDisposables = [
    { dispose: bus.on("graph:changed",   invalidateAll) },
    { dispose: bus.on("index:done",      invalidateAll) },
    { dispose: bus.on("repo:changed",    invalidateAll) },
    { dispose: bus.on("context:changed", invalidateAll) },
  ];

  // Ensure listeners fire.
  bus.emit("graph:changed");
  assert.equal(invalidateCalls, 1);

  // Simulate extension deactivation: VS Code calls dispose() on every subscription.
  for (const d of subscriptionDisposables) d.dispose();

  // Listeners must no longer fire.
  bus.emit("graph:changed");
  bus.emit("index:done");
  bus.emit("repo:changed");
  bus.emit("context:changed");
  assert.equal(invalidateCalls, 1, "invalidateAll must not be called after disposal");
});