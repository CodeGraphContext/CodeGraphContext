import React, { useState, useEffect } from 'react';
import { Activity, Database, FileCode2, Network } from 'lucide-react';
import { IndexingStatusCard } from './IndexingStatusCard';

export function IndexingMetricsPanel() {
  const [metrics, setMetrics] = useState({
    active_repositories: 0,
    files_analyzed: 0,
    graph_nodes_created: 0,
    indexing_rate: 0
  });

  useEffect(() => {
    const eventSource = new EventSource('http://localhost:8000/api/v1/telemetry/sse');

    eventSource.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.event === 'metrics_snapshot' || payload.event === 'metrics_update') {
          setMetrics(prev => ({
            ...prev,
            ...payload.data
          }));
        }
      } catch (e) {
        console.error("Error parsing telemetry metrics:", e);
      }
    };

    return () => {
      eventSource.close();
    };
  }, []);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
      <IndexingStatusCard 
        title="Active Repositories" 
        value={metrics.active_repositories.toLocaleString()} 
        icon={Database} 
        status={metrics.active_repositories > 0 ? "healthy" : "warning"} 
      />
      <IndexingStatusCard 
        title="Files Analyzed" 
        value={metrics.files_analyzed.toLocaleString()} 
        icon={FileCode2} 
        status="healthy" 
        pulse={metrics.files_analyzed > 0}
      />
      <IndexingStatusCard 
        title="Graph Nodes Created" 
        value={metrics.graph_nodes_created.toLocaleString()} 
        icon={Network} 
        status="healthy" 
      />
      <IndexingStatusCard 
        title="Indexing Rate (files/sec)" 
        value={metrics.indexing_rate.toLocaleString()} 
        icon={Activity} 
        status="healthy" 
        pulse={metrics.indexing_rate > 0}
      />
    </div>
  );
}
