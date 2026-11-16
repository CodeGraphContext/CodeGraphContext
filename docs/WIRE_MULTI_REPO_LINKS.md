# Wire / MULTI_REPO_LINKS — Developer Guide

`wire` is CGC's cross-repo coupling detector. It finds where one repo
*produces* to a Kafka topic, calls an HTTP/gRPC endpoint, etc., and another
repo *consumes*/*serves* the same thing — and materializes that as graph
edges (`PRODUCES_TO`, `CONSUMES_FROM`, `SERVES`, `INVOKES`) so an agent can
answer "who else talks to this topic?" with one Cypher query instead of
grepping N repos.

Everything in this doc is gated behind the `MULTI_REPO_LINKS` feature flag —
when it's off, none of this runs and indexing behaves exactly as it did
before this feature existed.

## 1. Enable the flag

```bash
cgc config set MULTI_REPO_LINKS true
```

This persists to `~/.codegraphcontext/.env`. Every `wire` subcommand prints
a yellow reminder if the flag is currently off.

Turning it off again (`cgc config set MULTI_REPO_LINKS false`) fully
disables the feature: the wire extraction step doesn't run during indexing,
no `Topic`/`Endpoint` nodes are created, and core `Function`/`Class`/`CALLS`
indexing is unaffected either way — the flag only gates the additive wire
pipeline, never the base graph.

## 2. Index the repos you want linked into one shared context

Cross-repo matching only works when the repos share a graph context —
`wire` compares nodes it can see in the *current* context, not across
separate databases.

```bash
cgc context create demo-services --database falkordb

cgc index /path/to/orders                       --context demo-services
cgc index /path/to/notification-worker  --context demo-services
cgc index /path/to/event-processor      --context demo-services
cgc index /path/to/status-gateway         --context demo-services
```

Re-index a repo any time with `--force` after code changes.

## 3. See what matched

```bash
cgc wire links --context demo-services
```

This queries the graph directly and prints:
- **matched Kafka topics** — at least one producer and one consumer found
- **orphan producers/consumers** — one side found, no counterpart yet
- **matched endpoints** / **orphan servers/clients** — same idea for HTTP/gRPC

JSON output: `cgc wire links --context demo-services --format json`.

### Preview without indexing

Before committing to a full index, you can preview what the extractors would
find on-disk, with nothing written to the graph:

```bash
cgc wire extract kafka --repo /path/to/orders
cgc wire extract http  --repo /path/to/orders
cgc wire extract grpc  --repo /path/to/orders
cgc wire discover --repo /path/to/orders --repo /path/to/notification-worker
```

`wire discover` aggregates multiple `--repo` roots the same way `wire links`
does over the graph, but works straight off the filesystem.

## 4. Confidence tiers

Every producer/consumer/server/client record gets a confidence tier:

| Tier | Meaning |
|---|---|
| `DECLARED` | Came from a `.cgc/wire.yml` hint file (see §6) — always trusted, outranks everything else |
| `EXTRACTED` | Literal string found directly in source (`new ProducerRecord("orders", ...)`) |
| `INFERRED` | A `${...}` placeholder that `ConfigValueStore` resolved to a literal, or a YAML config binding (see §5) |
| `NORMALIZED` | Cleaned-up/canonicalized form of another tier |
| `SYMBOLIC` | A `${...}` placeholder that could **not** be resolved — matched on the placeholder string itself |
| `AMBIGUOUS` | A regex `topicPattern`, or an identifier CGC couldn't trace to a literal — **excluded** from `wire links`/`wire suggest` unless you pass `include_ambiguous` |

`wire links`, `wire discover`, and indexing all treat everything except
`AMBIGUOUS` as usable (`HIGH_CONFIDENCE_TIERS` in `wire/writer.py`).

## 5. Config-driven bindings (YAML, no code call site)

Some services (Guice/Dropwizard style) register Kafka producers/consumers
entirely through YAML config, with no `@KafkaListener` or
`new ProducerRecord(...)` anywhere in the Java source. The extractor detects
this pattern directly from config: a `topicName`/`topic` key with a sibling
`consumingEnabled` / `producingEnabled` / `publishingEnabled: true` key
under the same parent block, e.g.:

```yaml
kafkaConfiguration:
  clusterConfigs:
    - topicName: order-events
      consumingEnabled: true
```

These records get `confidence: INFERRED` and an `fqn` like
`config:kafkaConfiguration.clusterConfigs[0]` — there's no backing
`:Function` node, so the writer anchors the edge on the YAML's `:File` node
instead (`coalesce(fn.name, '(config)')` shows up as `(config)` in
`wire links` output for these rows).

Inspect what the config scanner sees directly:

```bash
cgc wire config list --repo /path/to/notification-worker
cgc wire config resolve '${kafka.topic.orders}' --repo /path/to/orders
```

**Known limitation:** when a key exists in multiple non-profile-suffixed
files (e.g. `prod.yml`, `dev.yml`, `e2e.yml` all define
`clusterConfigs[0].topicName` under the same path), `ConfigValueStore` keeps
whatever file it scanned last — so the resolved literal may be an
environment variant (`order-events_e2e`) rather than the production value
(`order-events`). The topic *coupling* is still correctly detected; only
the exact string shown may be from a non-prod profile.

## 6. Declaring hints by hand (`.cgc/wire.yml`)

When extraction can't resolve something (ambiguous identifier, cross-team
naming drift, etc.), declare the coupling explicitly in a repo's
`.cgc/wire.yml`. Declared hints are always `DECLARED` tier and outrank
anything auto-extracted.

Get a fully-commented template:

```bash
cgc wire example > .cgc/wire.yml
```

Schema:

```yaml
version: 1

topics:
  - system: kafka
    name: order-events
    produced_by:
      - orders.impl.KafkaPublisherImpl.publish
    consumed_by:
      - event_processor.OrderEventHandler.handle
      - notification_worker.KafkaMessageConsumer.consume

endpoints:
  - protocol: grpc
    method: GetStatus
    path: com.example.status.v1.StatusService/GetStatus
    served_by:
      - status_gateway.StatusServiceGRPC.getStatus
    invoked_by:
      - orders.client.StatusClient.getStatus

aliases:
  topics:
    - canonical: order-events
      names:
        - order.events
        - order_events_v2
  endpoints: []
```

`produced_by`/`served_by`/etc. are fully-qualified names matching the FQN
CGC stores on `Function` nodes.

Validate before committing:

```bash
cgc wire validate .cgc/wire.yml
```

Inspect merged hints across all sources (CLI / `CGC_WIRE` env var / context /
repo `.cgc/wire.yml`) without touching the graph:

```bash
cgc wire list --context demo-services --repo /path/to/orders
cgc wire show --context demo-services --format yaml
```

## 7. Finding likely matches you haven't declared yet

`wire links` only matches on exact literal equality. Real topics often drift
by an environment suffix (`_e2e`, `_prod`) or a stray prefix and end up as
two disconnected orphans. `wire suggest` re-ranks every orphan pair by
string similarity, cross-repo only:

```bash
cgc wire suggest --context demo-services --min-score 0.6
```

- `--min-score` (default `0.6`) — lower it to see more/weaker candidates
- `--emit-hints-dir DIR` — writes draft `<repo>.suggested-wire.yml` files
  (one per repo, deduped keeping the highest-scoring candidate) for a human
  to review, fill in real FQNs, and move into `.cgc/wire.yml`. Nothing is
  auto-applied.

If the context has no known repo list, candidates show `?` instead of a
repo name (still useful for the topic/endpoint name matching, just without
repo attribution).

## 8. Quick end-to-end example (demo-services)

```bash
cgc config set MULTI_REPO_LINKS true

cgc context create demo-services --database falkordb
cgc index /path/to/demo-services/orders                      --context demo-services
cgc index /path/to/demo-services/notification-worker --context demo-services
cgc index /path/to/demo-services/event-processor      --context demo-services
cgc index /path/to/demo-services/status-gateway        --context demo-services

cgc wire links --context demo-services
# -> matched Kafka topics: 1 (order-events_e2e, orders <-> notification-worker)

cgc wire suggest --context demo-services
# -> 0 candidates once the real match above is already resolved
```

## 9. Instructing coding agents (Claude, Copilot) to query 1-hop

When an AI coding agent (Claude Code, GitHub Copilot, etc.) uses CGC to trace
a cross-repo wire coupling, it's easy for it to default to a wasteful
two-step pattern: one Cypher query to get a `path`/`line_number`, then a
separate `read_file` call to fetch the actual source. For point lookups this
roughly doubles round-trips and pulls back far more surrounding text than
needed. Returning `c.source` / `fn.source` **inline in the same Cypher
call** cuts both.

Add an instruction like this to the agent's custom instructions file
(`.github/copilot-instructions.md`, `CLAUDE.md`, or equivalent):

```markdown
## Querying CGC wire couplings

When tracing a producer/consumer or server/client pair found via
`cgc wire links` / `cgc wire discover`, fetch the implementation in the
SAME Cypher call — do not split it into "get path" then `read_file`.

Bad (2-hop):
  MATCH (fn:Function {name: 'publish'}) RETURN fn.path, fn.line_number
  # ...then a separate read_file on fn.path

Good (1-hop):
  MATCH (fn:Function {name: 'publish'}) RETURN fn.source, fn.path

Only fall back to `read_file` when you need surrounding context beyond a
single function/class body (e.g. imports, sibling methods).
```

This is a usage-pattern instruction, not a CGC flag — there's nothing to
enable in the tool itself. It applies to any CGC Cypher query, not just
`wire`, but matters most here because tracing a cross-repo coupling
naturally means looking up several `Function`/`File` nodes back to back
(the producer, the consumer, maybe a config file) — the 2-hop tax compounds
with each one.

## 10. Troubleshooting

| Symptom | Likely cause |
|---|---|
| `wire links` shows 0 matched topics but you know two repos share a topic | One side is config-driven only (§5) — confirm with `cgc wire extract kafka --repo <path>`; if it's not showing up there either, check the topic/enabled key names match `_TOPIC_KEY_LEAVES`/`_ENABLED_KEY_LEAVES` conventions |
| A match shows the wrong (non-prod) topic string | Multi-profile YAML last-file-wins limitation, see §5 |
| Yellow "`MULTI_REPO_LINKS` is off" notice on every command | Run `cgc config set MULTI_REPO_LINKS true` |
| `wire links`/`wire suggest` return nothing at all | Confirm the repos were indexed into the **same** `--context`, not separate ones |
| Consumer/producer shows `(config)` instead of a function name | Expected — that record is config-anchored (§5), it has no backing method |
