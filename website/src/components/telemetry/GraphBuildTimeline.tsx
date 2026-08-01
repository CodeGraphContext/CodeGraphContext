import React from 'react';
import { motion } from 'framer-motion';

export function GraphBuildTimeline() {
  const steps = [
    { label: 'File Parsing', progress: 100, status: 'complete' },
    { label: 'AST Generation', progress: 100, status: 'complete' },
    { label: 'Symbol Resolution', progress: 85, status: 'in_progress' },
    { label: 'Edge Construction', progress: 40, status: 'in_progress' },
    { label: 'Graph Layout', progress: 0, status: 'pending' },
  ];

  return (
    <div className="rounded-xl border border-white/10 bg-black/40 backdrop-blur-md p-6 h-[400px] flex flex-col">
      <h3 className="text-lg font-semibold text-white mb-6">Build Timeline</h3>
      <div className="flex-1 flex flex-col justify-between relative">
        <div className="absolute left-[15px] top-4 bottom-4 w-0.5 bg-white/10" />
        
        {steps.map((step, index) => (
          <div key={step.label} className="relative flex items-center gap-6 group">
            <div className={`relative z-10 w-8 h-8 rounded-full flex items-center justify-center border-2 transition-colors duration-500
              ${step.status === 'complete' ? 'border-emerald-500 bg-emerald-500/20 text-emerald-400' : 
                step.status === 'in_progress' ? 'border-amber-500 bg-amber-500/20 text-amber-400' : 
                'border-slate-700 bg-slate-800 text-slate-500'}`}
            >
              <span className="text-xs font-bold">{index + 1}</span>
              {step.status === 'in_progress' && (
                <span className="absolute w-12 h-12 rounded-full border-2 border-amber-500/30 animate-ping" />
              )}
            </div>
            
            <div className="flex-1">
              <div className="flex justify-between items-center mb-1">
                <span className={`text-sm font-medium ${step.status === 'pending' ? 'text-slate-500' : 'text-slate-200'}`}>
                  {step.label}
                </span>
                <span className={`text-xs ${step.status === 'pending' ? 'text-slate-600' : 'text-slate-400'}`}>
                  {step.progress}%
                </span>
              </div>
              
              <div className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden">
                <motion.div 
                  initial={{ width: 0 }}
                  animate={{ width: `${step.progress}%` }}
                  transition={{ duration: 1.5, ease: "easeOut" }}
                  className={`h-full rounded-full ${
                    step.status === 'complete' ? 'bg-emerald-500' : 'bg-amber-500 relative overflow-hidden'
                  }`}
                >
                  {step.status === 'in_progress' && (
                    <motion.div 
                      animate={{ x: ['-100%', '200%'] }}
                      transition={{ repeat: Infinity, duration: 1.5, ease: "linear" }}
                      className="absolute inset-0 bg-gradient-to-r from-transparent via-white/50 to-transparent w-1/2"
                    />
                  )}
                </motion.div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
