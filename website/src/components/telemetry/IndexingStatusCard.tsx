import React from 'react';
import { motion } from 'framer-motion';
import { LucideIcon } from 'lucide-react';

interface IndexingStatusCardProps {
  title: string;
  value: string | number;
  icon: LucideIcon;
  status?: 'healthy' | 'warning' | 'critical' | 'neutral';
  pulse?: boolean;
}

const statusColors = {
  healthy: 'text-emerald-500',
  warning: 'text-amber-500',
  critical: 'text-red-500',
  neutral: 'text-slate-400',
};

const bgColors = {
  healthy: 'bg-emerald-500/10',
  warning: 'bg-amber-500/10',
  critical: 'bg-red-500/10',
  neutral: 'bg-slate-400/10',
};

export function IndexingStatusCard({ title, value, icon: Icon, status = 'neutral', pulse = false }: IndexingStatusCardProps) {
  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="relative overflow-hidden rounded-xl border border-white/10 bg-black/40 backdrop-blur-md p-6"
    >
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-slate-400">{title}</p>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-3xl font-semibold text-white">{value}</span>
          </div>
        </div>
        <div className={`rounded-full p-3 ${bgColors[status]}`}>
          <Icon className={`h-6 w-6 ${statusColors[status]}`} />
        </div>
      </div>
      {pulse && (
        <span className="absolute right-6 top-6 flex h-3 w-3">
          <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${bgColors[status].replace('/10', '')}`}></span>
          <span className={`relative inline-flex rounded-full h-3 w-3 ${bgColors[status].replace('/10', '')}`}></span>
        </span>
      )}
    </motion.div>
  );
}
