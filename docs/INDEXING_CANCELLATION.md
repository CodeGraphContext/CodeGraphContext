# Indexing cancellation

The in-process `JobManager.cancel_job(job_id)` method requests cooperative cancellation of a full Tree-sitter or SCIP indexing job. It returns `True` for the first accepted request and `False` for an unknown job, a terminal job, or a repeated request. This is a core API; no MCP tool or HTTP cancellation endpoint is added.

```python
accepted = server.job_manager.cancel_job(job_id)
job = server.job_manager.get_job(job_id)
```

## Request and completion are separate

| State when requested | Immediate result | When work is quiescent |
| --- | --- | --- |
| Pending, before admission | `CANCELLED`, `cancel_requested=True`, `end_time` set | No pipeline is admitted |
| Running | `RUNNING`, `cancel_requested=True`, `end_time=None` | `CANCELLED`, with `end_time` set after workers finish |
| Completed, failed, or cancelled | Request rejected | Existing terminal result is retained |

`check_job_status` and `list_jobs` include `cancel_requested` through the existing job serialization. A running job with cancellation requested remains visible to active-job/path lookup, cleanup, and both local and global context-switch guards. A blocked admitted worker is not presumed crashed merely because it has not reported progress recently.

Admission, cancellation, and terminal publication use the same job-manager lock. If a cancellation request is accepted before final publication, cancellation wins over completion or failure. A real exception encountered while draining is retained in `errors`, `error_type`, and the bounded `traceback`. Once terminal, the job cannot be reopened or overwritten by late progress/completion callbacks.

## Cooperative boundaries

Tree-sitter checks before discovery, pre-scan, parse admission, graph writes, linking, and optional embedding/post-processing phases, and after blocking calls. Waiting parse tasks stop at the semaphore boundary; already admitted native parses are joined before finalization. SCIP checks between its subprocess, index parsing, parser loading, supplementary passes, writes, and linking. Cancellation does not enter the ordinary SCIP-to-Tree-sitter fallback path or a file-write retry/fallback.

An already running native call, database write, embedding batch, or SCIP subprocess is allowed to finish. Cancellation latency therefore includes that call's remaining runtime; there is no forced subprocess termination policy. The SCIP temporary directory remains owned until its subprocess and worker have finished. Already committed graph changes are retained: cancellation does not roll them back.

Once the pipeline is admitted, cancelling its **asyncio task** also requests cooperative cancellation. Its completion is delayed until the supervised pipeline and all admitted parse workers drain, including after repeated `Task.cancel()` calls. Use `cancel_job` for a pending job: an asyncio task cancelled before its coroutine starts cannot update the job record. Integrations must await the admitted task before closing its database or stopping its event loop.

Use `cancel_job` to request cancellation when scheduling with `asyncio.run_coroutine_threadsafe`. Calling `cancel()` on the returned **concurrent future** marks that wrapper cancelled immediately; the wrapper's terminal state alone is not proof that the asyncio task or its native worker has finished. This change does not add a server-wide shutdown registry or alter watcher shutdown. The application's existing shutdown owner must drain its scheduled work before releasing database resources.

## Validation

`tests/unit/tools/test_indexing_cancellation.py` exercises both real pipeline entry points with controlled worker barriers, pending admission, repeated task cancellation, phase boundaries, queued parse rejection, completion races, failure diagnostics, context-switch/cleanup guards, and cancellation without SCIP fallback. Its subprocess case starts an owned Python child and verifies natural exit and temporary-directory cleanup before the cancelled task completes. `tests/unit/tools/test_indexing_gateway_liveness.py` verifies that health requests remain responsive while indexing is blocked and that a cancelled SCIP worker does not enter later graph writes.

Run the required unit and integration gate with `./tests/run_tests.sh fast`.
