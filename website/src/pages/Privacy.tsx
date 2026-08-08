import React from "react";
import { motion } from "framer-motion";
import { Shield, Database, Lock, RefreshCw, Mail } from "lucide-react";

const Privacy: React.FC = () => {
  return (
    <main className="min-h-screen bg-background pt-32 md:pt-36 pb-20 px-6 flex flex-col items-center relative overflow-hidden">
      {/* Decorative ambient background glows */}
      <div className="absolute top-1/4 left-1/4 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-purple-500/10 rounded-full blur-[140px] pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/4 translate-x-1/2 translate-y-1/2 w-96 h-96 bg-blue-500/10 rounded-full blur-[140px] pointer-events-none" />

      <div className="w-full max-w-4xl relative z-10">
        {/* Header Section */}
        <div className="text-center mb-16">
          <motion.div
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ duration: 0.5 }}
            className="inline-flex p-3 rounded-2xl bg-purple-500/10 text-purple-400 border border-purple-500/20 mb-6 drop-shadow-[0_0_15px_rgba(168,85,247,0.2)]"
          >
            <Shield className="w-8 h-8" />
          </motion.div>
          
          <h1 className="text-4xl md:text-5xl font-extrabold mb-4 bg-gradient-to-r from-white via-zinc-200 to-zinc-400 bg-clip-text text-transparent tracking-tight">
            Privacy Policy
          </h1>
          <p className="text-zinc-400 text-lg max-w-2xl mx-auto">
            CodeGraphContext respects your privacy. Because of our revolutionary client-side design, your code never leaves your local machine.
          </p>
        </div>

        {/* Content Cards Grid */}
        <div className="grid gap-8 md:grid-cols-2 mb-12">
          {/* Card 1: Local-First Parsing */}
          <motion.div
            initial={{ y: 25, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.1 }}
            className="p-8 rounded-3xl border border-white/10 bg-zinc-950/40 backdrop-blur-xl relative overflow-hidden group hover:border-purple-500/30 transition-all duration-300"
          >
            <div className="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-purple-500 to-indigo-500 opacity-50" />
            <Database className="w-8 h-8 text-purple-400 mb-4" />
            <h3 className="text-xl font-bold text-white mb-2">100% Client-Side Parsing</h3>
            <p className="text-zinc-400 text-sm leading-relaxed">
              When you index a repository via local upload or GitHub Fetch, our lightweight WebAssembly Tree-Sitter parser extracts AST nodes and links **entirely in your own browser's background web worker thread**. Absolutely zero files or raw code contents are ever uploaded to our servers or processed in the cloud.
            </p>
          </motion.div>

          {/* Card 2: Local Storage */}
          <motion.div
            initial={{ y: 25, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.2 }}
            className="p-8 rounded-3xl border border-white/10 bg-zinc-950/40 backdrop-blur-xl relative overflow-hidden group hover:border-blue-500/30 transition-all duration-300"
          >
            <div className="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-blue-500 to-cyan-500 opacity-50" />
            <Lock className="w-8 h-8 text-blue-400 mb-4" />
            <h3 className="text-xl font-bold text-white mb-2">Private Local Caching</h3>
            <p className="text-zinc-400 text-sm leading-relaxed">
              All parsed code graph relationships (nodes and links) are saved directly in your browser's local **IndexedDB cache**. They stay securely stored on your own physical drive. No account sign-up is required, and we do not compile any profile or store analytics on your indexed files.
            </p>
          </motion.div>

          {/* Card 3: Realtime Tunneling */}
          <motion.div
            initial={{ y: 25, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.3 }}
            className="p-8 rounded-3xl border border-white/10 bg-zinc-950/40 backdrop-blur-xl relative overflow-hidden group hover:border-indigo-500/30 transition-all duration-300"
          >
            <div className="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-indigo-500 to-purple-500 opacity-50" />
            <RefreshCw className="w-8 h-8 text-indigo-400 mb-4" />
            <h3 className="text-xl font-bold text-white mb-2">Ephemeral Signaling Tunnels</h3>
            <p className="text-zinc-400 text-sm leading-relaxed">
              ChatGPT Custom Actions query your browser dashboard using transient realtime broadcast channels powered by Supabase. These messages are completely stateless and ephemeral. They route queries and results immediately, without keeping any long-term logs or storing analysis payloads on our servers.
            </p>
          </motion.div>

          {/* Card 4: Control & Deletion */}
          <motion.div
            initial={{ y: 25, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.4 }}
            className="p-8 rounded-3xl border border-white/10 bg-zinc-950/40 backdrop-blur-xl relative overflow-hidden group hover:border-pink-500/30 transition-all duration-300"
          >
            <div className="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-pink-500 to-rose-500 opacity-50" />
            <Shield className="w-8 h-8 text-pink-400 mb-4" />
            <h3 className="text-xl font-bold text-white mb-2">Data Retention & Deletion</h3>
            <p className="text-zinc-400 text-sm leading-relaxed">
              Because all data is stored on your own device, you have complete control over it. You can instantly delete all cached repository code graphs at any time by clearing your browser's cookies and site data, or by clicking "Clear Cache" directly within the visualizer dashboard.
            </p>
          </motion.div>
        </div>

        {/* Contact Info Footer Section */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
          className="p-8 rounded-3xl border border-white/10 bg-gradient-to-b from-white/5 to-white/[0.01] text-center w-full flex flex-col items-center gap-4 relative overflow-hidden"
        >
          <Mail className="w-6 h-6 text-purple-400" />
          <div>
            <h3 className="text-lg font-bold text-white">Have Questions?</h3>
            <p className="text-zinc-400 text-sm mt-1 max-w-[400px] leading-relaxed mx-auto">
              If you have any questions about this privacy policy or our local-first graph architecture, please feel free to reach out to us at:
            </p>
          </div>
          <a
            href="mailto:support@cgc.codes"
            className="px-6 py-2.5 rounded-full bg-purple-500/10 hover:bg-purple-500 hover:text-white border border-purple-500/20 text-purple-300 text-sm font-semibold transition-all duration-300"
          >
            support@cgc.codes
          </a>
        </motion.div>
      </div>
    </main>
  );
};

export default Privacy;
