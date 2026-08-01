import React from 'react';
import { IndexingMetricsPanel } from '../components/telemetry/IndexingMetricsPanel';
import { RepositoryTelemetryGrid } from '../components/telemetry/RepositoryTelemetryGrid';
import { motion } from 'framer-motion';

export default function TelemetryDashboard() {
  return (
    <div className="min-h-screen bg-black text-slate-200 selection:bg-emerald-500/30">
      <main className="container mx-auto px-6 py-24">
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-12"
        >
          <div className="flex items-center gap-4 mb-2">
            <h1 className="text-4xl font-bold tracking-tight text-white">
              Realtime Indexing Telemetry
            </h1>
            <span className="flex h-3 w-3 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
            </span>
          </div>
          <p className="text-slate-400 text-lg">
            Command center for observing codebase parsing, AST generation, and graph indexing operations.
          </p>
        </motion.div>

        <IndexingMetricsPanel />
        <RepositoryTelemetryGrid />
        
      </main>
    </div>
  );
}
