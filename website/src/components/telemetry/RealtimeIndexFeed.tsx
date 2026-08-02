import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle2, FileJson, FileText, Database } from 'lucide-react';

interface FeedItem {
  id: string;
  type: 'parsed' | 'node_created' | 'edge_created';
  message: string;
  timestamp: Date;
}

export function RealtimeIndexFeed() {
  const [feed, setFeed] = useState<FeedItem[]>([]);

  useEffect(() => {
    const types: Array<'parsed' | 'node_created' | 'edge_created'> = ['parsed', 'node_created', 'edge_created'];
    const messages = [
      'Parsed components/Button.tsx',
      'Created AST node for Button',
      'Linked Button to ThemeProvider',
      'Parsed lib/utils.ts',
      'Created AST node for cn()',
      'Analyzed dependencies for UserContext',
      'Parsed pages/Dashboard.tsx'
    ];

    const interval = setInterval(() => {
      setFeed(prev => {
        const newItem: FeedItem = {
          id: Math.random().toString(36).substring(7),
          type: types[Math.floor(Math.random() * types.length)],
          message: messages[Math.floor(Math.random() * messages.length)],
          timestamp: new Date()
        };
        return [newItem, ...prev].slice(0, 8);
      });
    }, 1500);

    return () => clearInterval(interval);
  }, []);

  const getIcon = (type: string) => {
    switch (type) {
      case 'parsed': return <FileText className="w-4 h-4 text-emerald-400" />;
      case 'node_created': return <Database className="w-4 h-4 text-amber-400" />;
      case 'edge_created': return <CheckCircle2 className="w-4 h-4 text-blue-400" />;
      default: return <FileJson className="w-4 h-4 text-slate-400" />;
    }
  };

  return (
    <div className="rounded-xl border border-white/10 bg-black/40 backdrop-blur-md p-6 h-[400px] overflow-hidden flex flex-col">
      <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
          <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
        </span>
        Live Indexing Feed
      </h3>
      <div className="flex-1 overflow-hidden relative">
        <AnimatePresence>
          {feed.map((item) => (
            <motion.div
              key={item.id}
              initial={{ opacity: 0, x: -20, height: 0 }}
              animate={{ opacity: 1, x: 0, height: 'auto' }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ duration: 0.3 }}
              className="flex items-center gap-3 py-3 border-b border-white/5 last:border-0"
            >
              <div className="p-2 rounded-md bg-white/5">
                {getIcon(item.type)}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-200 truncate">
                  {item.message}
                </p>
                <p className="text-xs text-slate-500">
                  {item.timestamp.toLocaleTimeString()}
                </p>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}
