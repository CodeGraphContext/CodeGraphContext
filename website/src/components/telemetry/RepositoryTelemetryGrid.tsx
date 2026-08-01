import React from 'react';
import { RealtimeIndexFeed } from './RealtimeIndexFeed';
import { GraphBuildTimeline } from './GraphBuildTimeline';

export function RepositoryTelemetryGrid() {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <GraphBuildTimeline />
      <RealtimeIndexFeed />
    </div>
  );
}
