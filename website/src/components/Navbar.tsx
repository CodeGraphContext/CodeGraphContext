import React, { useState, useEffect } from "react";
import { ThemeToggle } from "@/components/ThemeToggle";

function handleScroll(e: React.MouseEvent<HTMLAnchorElement>) {
  const href = e.currentTarget.getAttribute('href');
  if (href && href.startsWith('#')) {
    e.preventDefault();
    const id = href.replace('#', '');
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }
}

const Navbar: React.FC = () => {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handleWindowScroll = () => {
      setScrolled(window.scrollY > 20);
    };
    window.addEventListener('scroll', handleWindowScroll);
    return () => window.removeEventListener('scroll', handleWindowScroll);
  }, []);

  return (
    <nav className={`fixed top-0 inset-x-0 z-50 transition-all duration-300 ${scrolled ? 'py-3 backdrop-blur-xl bg-background/60 border-b border-white/5 shadow-sm' : 'py-5 bg-transparent'}`}>
      <div className="container mx-auto px-6 max-w-7xl flex items-center justify-between">
        <div className="flex items-center gap-2">
          {/* A small aesthetic dot for brand feel */}
          <div className="w-3 h-3 rounded-full bg-primary/80 shadow-[0_0_10px_rgba(139,92,246,0.6)] animate-pulse" />
          <span className="font-bold text-lg tracking-tight">CodeGraphContext</span>
        </div>

        <ul className="hidden md:flex items-center gap-8 font-medium text-sm text-foreground/80">
          <li><a href="#features" className="hover:text-primary transition-colors" onClick={handleScroll}>Features</a></li>
          <li><a href="#bundleregistry" className="hover:text-primary transition-colors" onClick={handleScroll}>Registry</a></li>
          <li><a href="#examples" className="hover:text-primary transition-colors" onClick={handleScroll}>Examples</a></li>
          <li><a href="#cookbook" className="hover:text-primary transition-colors" onClick={handleScroll}>Cookbook</a></li>
        </ul>

        <div className="flex items-center gap-4">
          <a href="https://github.com/CodeGraphContext/CodeGraphContext" target="_blank" rel="noreferrer" className="hidden sm:block text-sm font-medium text-foreground/80 hover:text-white transition-colors">
            GitHub
          </a>
          <a href="#installation" onClick={handleScroll} className="bg-white/10 hover:bg-white/20 border border-white/10 backdrop-blur-md px-4 py-2 rounded-full text-sm font-medium transition-all duration-300">
            Install Let's Go
          </a>
          {/* Header with Theme Toggle */}
      
        <div>
            <ThemeToggle />
        </div>
      
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
