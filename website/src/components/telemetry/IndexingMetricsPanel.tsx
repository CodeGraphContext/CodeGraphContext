import React from 'react';
import { Activity, Database, FileCode2, Network } from 'lucide-react';
import { IndexingStatusCard } from './IndexingStatusCard';

export function IndexingMetricsPanel() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
      <IndexingStatusCard 
        title="Active Repositories" 
        value="3" 
        icon={Database} 
        status="healthy" 
      />
      <IndexingStatusCard 
        title="Files Analyzed" 
        value="12,458" 
        icon={FileCode2} 
        status="healthy" 
        pulse={true}
      />
      <IndexingStatusCard 
        title="Graph Nodes Created" 
        value="48,932" 
        icon={Network} 
        status="warning" 
      />
      <IndexingStatusCard 
        title="Indexing Rate (files/sec)" 
        value="42" 
        icon={Activity} 
        status="healthy" 
        pulse={true}
      />
    </div>
  );
}
