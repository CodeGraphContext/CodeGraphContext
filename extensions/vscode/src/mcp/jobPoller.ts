import * as vscode from "vscode";
import { CgcService } from "./service";
import { cgcEvents } from "./eventBus";

/**
 * Polls `check_job_status` for active indexing jobs and fires EventBus events.
 * Attach to the extension context as a disposable.
 */
export class JobPoller implements vscode.Disposable {
  private readonly activeJobs = new Map<string, NodeJS.Timeout>();

  constructor(private readonly service: CgcService) {}

  /**
   * Start polling a job ID every 2 seconds.
   * Fires index:progress / index:done / index:failed on the event bus.
   */
  public startPolling(jobId: string): void {
    if (this.activeJobs.has(jobId)) return;

    cgcEvents.emit("index:started", { jobId });

    const interval = setInterval(async () => {
      try {
        const status = await this.service.checkJobStatus(jobId);
        const pct = status.progress ?? 0;

        if (status.status === "running" || status.status === "pending") {
          cgcEvents.emit("index:progress", { jobId, pct, message: status.message });
        } else if (status.status === "completed") {
          cgcEvents.emit("index:done", { jobId });
          this._stop(jobId);
        } else if (status.status === "failed") {
          cgcEvents.emit("index:failed", { jobId, error: status.error ?? status.message });
          this._stop(jobId);
        }
      } catch {
        // If the job status call fails, just stop polling silently
        this._stop(jobId);
      }
    }, 2000);

    this.activeJobs.set(jobId, interval);
  }

  private _stop(jobId: string): void {
    const timer = this.activeJobs.get(jobId);
    if (timer) {
      clearInterval(timer);
      this.activeJobs.delete(jobId);
    }
  }

  public dispose(): void {
    for (const [id] of this.activeJobs) {
      this._stop(id);
    }
  }
}
