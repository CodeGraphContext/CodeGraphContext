import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Code2, GitBranch, CheckCircle, Zap, Users } from "lucide-react";
import { Loader2 } from "lucide-react";
import Footer from "../components/Footer";

const Contributing: React.FC = () => {
  const [content, setContent] = useState<string>("");
  const [isLoading, setIsLoading] = useState(true);
  const [tableOfContents, setTableOfContents] = useState<Array<{ title: string; id: string }>>([]);

  // Fetch CONTRIBUTING.md from GitHub
  useEffect(() => {
    const fetchContributing = async () => {
      try {
        const response = await fetch(
          "https://raw.githubusercontent.com/CodeGraphContext/CodeGraphContext/main/CONTRIBUTING.md"
        );
        if (!response.ok) throw new Error("Failed to fetch CONTRIBUTING.md");

        const text = await response.text();
        
        // Extract headings for TOC
        const headings = text.match(/^## .+$/gm) || [];
        const toc = headings.map((heading) => ({
          title: heading.replace(/^## /, ""),
          id: heading
            .replace(/^## /, "")
            .toLowerCase()
            .replace(/\s+/g, "-"),
        }));
        setTableOfContents(toc);

        // Convert markdown to HTML
        const htmlContent = convertMarkdownToHtml(text);
        setContent(htmlContent);
      } catch (error) {
        console.error("Error fetching CONTRIBUTING.md:", error);
        setContent("<p>Failed to load contribution guidelines</p>");
      } finally {
        setIsLoading(false);
      }
    };

    fetchContributing();
  }, []);

  // Convert markdown to basic HTML
  const convertMarkdownToHtml = (markdown: string): string => {
    let html = markdown
      // Headers
      .replace(/^### (.+)$/gm, "<h3>$1</h3>")
      .replace(/^## (.+)$/gm, (match, p1) => {
        const id = p1.toLowerCase().replace(/\s+/g, "-");
        return '<h2 id="${id}">${p1}</h2>';
      })
      .replace(/^# (.+)$/gm, "<h1>$1</h1>")
      // Bold and italic
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.+?)\*/g, "<em>$1</em>")
      // Code blocks
      .replace(/```bash\n([\s\S]*?)```/g, '<pre class="code-block"><code class="language-bash">$1</code></pre>')
      .replace(/```python\n([\s\S]*?)```/g, '<pre class="code-block"><code class="language-python">$1</code></pre>')
      .replace(/```\n([\s\S]*?)```/g, '<pre class="code-block"><code>$1</code></pre>')
      // Inline code
      .replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')
      // Links
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
      // Bullet lists
      .replace(/^\* (.+)$/gm, "<li>$1</li>")
      .replace(/(<li>.*<\/li>)/s, (match) => `<ul>${match}</ul>`)
      // Numbered lists
      .replace(/^\d+\. (.+)$/gm, "<li>$1</li>")
      // Paragraphs
      .replace(/\n\n/g, "</p><p>")
      .replace(/^(?!<[a-z/])/gm, "<p>");

    return html;
  };

  if (isLoading) {
    return (
      <main className="min-h-screen bg-background pt-32 md:pt-36 pb-12 px-6 flex flex-col items-center">
        <div className="flex flex-col items-center justify-center gap-4">
          <Loader2 className="w-12 h-12 animate-spin text-purple-500" />
          <p className="text-[10px] font-mono uppercase tracking-widest text-gray-500">
            Loading contribution guidelines...
          </p>
        </div>
        <Footer />
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-background pt-32 md:pt-36 pb-20 px-6 flex flex-col items-center relative overflow-hidden">
      {/* Decorative ambient background glows */}
      <div className="absolute top-1/4 left-1/4 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-purple-500/10 rounded-full blur-[140px] pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/4 translate-x-1/2 translate-y-1/2 w-96 h-96 bg-blue-500/10 rounded-full blur-[140px] pointer-events-none" />

      <div className="w-full max-w-5xl relative z-10">
        {/* Header Section */}
        <div className="text-center mb-16">
          <motion.div
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ duration: 0.5 }}
            className="inline-flex p-3 rounded-2xl bg-purple-500/10 text-purple-400 border border-purple-500/20 mb-6 drop-shadow-[0_0_15px_rgba(168,85,247,0.2)]"
          >
            <Code2 className="w-8 h-8" />
          </motion.div>
          
          <h1 className="text-4xl md:text-5xl font-extrabold mb-4 bg-gradient-to-r from-white via-zinc-200 to-zinc-400 bg-clip-text text-transparent tracking-tight">
            Contributing to CodeGraphContext
          </h1>
          <p className="text-zinc-400 text-lg max-w-2xl mx-auto">
            We welcome contributions from the community. This guide will help you get started with development and submitting changes.
          </p>
        </div>

        {/* Quick Start Cards */}
        <div className="grid gap-4 md:grid-cols-3 mb-12">
          <motion.div
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.1 }}
            className="p-6 rounded-2xl border border-white/10 bg-zinc-950/40 backdrop-blur-xl hover:border-purple-500/30 transition-all"
          >
            <GitBranch className="w-6 h-6 text-purple-400 mb-3" />
            <h3 className="font-bold text-white mb-2">Fork & Branch</h3>
            <p className="text-sm text-zinc-400">Create a feature branch from main for your changes.</p>
          </motion.div>

          <motion.div
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.2 }}
            className="p-6 rounded-2xl border border-white/10 bg-zinc-950/40 backdrop-blur-xl hover:border-blue-500/30 transition-all"
          >
            <Zap className="w-6 h-6 text-blue-400 mb-3" />
            <h3 className="font-bold text-white mb-2">Code & Test</h3>
            <p className="text-sm text-zinc-400">Follow PEP 8 standards and include unit tests.</p>
          </motion.div>

          <motion.div
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.3 }}
            className="p-6 rounded-2xl border border-white/10 bg-zinc-950/40 backdrop-blur-xl hover:border-green-500/30 transition-all"
          >
            <CheckCircle className="w-6 h-6 text-green-400 mb-3" />
            <h3 className="font-bold text-white mb-2">Submit PR</h3>
            <p className="text-sm text-zinc-400">Open a pull request with clear description.</p>
          </motion.div>
        </div>

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-8 mb-12">
          {/* Table of Contents Sidebar */}
          <aside className="lg:col-span-1">
            <motion.div
              initial={{ y: 20, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: 0.4 }}
              className="sticky top-32 p-6 rounded-2xl border border-white/10 bg-zinc-950/40 backdrop-blur-xl"
            >
              <h3 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
                <Users className="w-4 h-4" />
                On This Page
              </h3>
              <nav className="space-y-2">
                {tableOfContents.map((item) => (
                  <a
                    key={item.id}
                    href={`#${item.id}`}
                    className="block text-sm text-zinc-400 hover:text-purple-400 transition-colors py-1 px-2 rounded hover:bg-white/5"
                  >
                    {item.title}
                  </a>
                ))}
              </nav>
            </motion.div>
          </aside>

          {/* Article Content */}
          <article className="lg:col-span-3">
            <motion.div
              initial={{ y: 20, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: 0.5 }}
              className="prose prose-invert max-w-none"
            >
              <div 
                className="contributing-content"
                dangerouslySetInnerHTML={{ __html: content }} 
              />
            </motion.div>

            {/* Call to Action */}
            <motion.div
              initial={{ y: 20, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: 0.6 }}
              className="mt-12 p-8 rounded-3xl border border-white/10 bg-gradient-to-b from-white/5 to-white/[0.01] relative overflow-hidden"
            >
              <div className="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-purple-500 to-blue-500 opacity-50" />
              
              <h3 className="text-2xl font-bold text-white mb-3">Ready to contribute?</h3>
              <p className="text-zinc-400 mb-6">
                Follow the guidelines above and submit your pull request to help improve CodeGraphContext. We look forward to your contribution!
              </p>
              <a
                href="https://github.com/CodeGraphContext/CodeGraphContext"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 text-white font-bold rounded-full transition-all duration-300"
              >
                <span>Visit GitHub Repository</span>
                <span>→</span>
              </a>
            </motion.div>
          </article>
        </div>
      </div>

      <Footer />
    </main>
  );
};

export default Contributing;
