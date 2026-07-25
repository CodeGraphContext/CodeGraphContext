import React, { useState, useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { Sparkles, ArrowLeft, Github, Menu, X, Box } from "lucide-react";

import MagneticButton from "./MagneticButton";

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
  const location = useLocation();
  const isLandingPage = location.pathname === "/" || location.pathname === "/pre-indexed";
  const [isOpen, setIsOpen] = useState(false);
  const [activeAnchor, setActiveAnchor] = useState<string>("");
  const [isScrolled, setIsScrolled] = useState(false);

  // Track active anchor on scroll
  useEffect(() => {
    const handleWindowScroll = () => {
      setIsScrolled(window.scrollY > 0);
      
      const anchors = ['features', 'bundle-registry', 'cookbook', 'demo', 'installation'];
      for (const anchor of anchors) {
        const el = document.getElementById(anchor);
        if (el) {
          const rect = el.getBoundingClientRect();
          if (rect.top <= 80 && rect.bottom >= 80) {
            setActiveAnchor(anchor);
            break;
          }
        }
      }
    };

    window.addEventListener('scroll', handleWindowScroll);
    return () => window.removeEventListener('scroll', handleWindowScroll);
  }, []);

  return (
    <nav className="fixed top-0 left-0 z-50 w-full select-none animate-in fade-in slide-in-from-top-4 duration-500" style={{ backdropFilter: 'blur(10px)' }}>
      <div className="w-full max-w-7xl mx-auto px-4 md:px-6 h-14 md:h-16 flex items-center justify-between" style={{ backgroundColor: isScrolled ? 'rgba(0, 0, 0, 0.65)' : 'rgba(0, 0, 0, 0.5)' }}>
        <style>{`
          nav {
            background: linear-gradient(180deg, rgba(0, 0, 0, 0.7) 0%, rgba(10, 10, 20, 0.6) 100%);
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            transition: background-color 0.3s ease;
          }
        `}</style>
        
        {/* Left: Brand Logo & Title */}
        <Link to="/" className="flex items-center gap-2 md:gap-3 mr-4 shrink-0 group transition-transform duration-300 hover:scale-105">
          <img
            src="/cgcIcon.png"
            className="w-7 h-7 md:w-8 md:h-8 transition-all duration-300 group-hover:scale-110 group-hover:drop-shadow-[0_0_8px_rgba(168,85,247,0.4)]"
            alt="CodeGraphContext Logo"
          />
          <span className="font-black text-sm md:text-lg gradient-text tracking-tighter uppercase block transition-all duration-300 group-hover:drop-shadow-[0_0_12px_rgba(168,85,247,0.3)]">
            CodeGraphContext
          </span>
        </Link>

        {/* Center: Anchors (Only displayed on landing page for optimal UX) */}
        {isLandingPage && (
          <ul className="hidden lg:flex items-center gap-6 font-bold text-[10px] uppercase tracking-widest text-gray-400">
            <li>
              <a 
                href="#features"
                className={`relative py-2 transition-all duration-300 group ${activeAnchor === 'features' ? 'text-white' : 'hover:text-white'}`}
                onClick={handleScroll}
              >
                Features
                <span className={`absolute bottom-0 left-0 h-0.5 bg-gradient-to-r from-purple-500 to-cyan-500 transition-all duration-300 ${activeAnchor === 'features' ? 'w-full' : 'w-0 group-hover:w-full'}`}></span>
              </a>
            </li>
            <li>
              <a 
                href="#bundle-registry"
                className={`relative py-2 transition-all duration-300 group ${activeAnchor === 'bundle-registry' ? 'text-white' : 'hover:text-white'}`}
                onClick={handleScroll}
              >
                Pre-indexed
                <span className={`absolute bottom-0 left-0 h-0.5 bg-gradient-to-r from-purple-500 to-cyan-500 transition-all duration-300 ${activeAnchor === 'bundle-registry' ? 'w-full' : 'w-0 group-hover:w-full'}`}></span>
              </a>
            </li>
            <li>
              <a 
                href="#cookbook"
                className={`relative py-2 transition-all duration-300 group ${activeAnchor === 'cookbook' ? 'text-white' : 'hover:text-white'}`}
                onClick={handleScroll}
              >
                Cookbook
                <span className={`absolute bottom-0 left-0 h-0.5 bg-gradient-to-r from-purple-500 to-cyan-500 transition-all duration-300 ${activeAnchor === 'cookbook' ? 'w-full' : 'w-0 group-hover:w-full'}`}></span>
              </a>
            </li>
            <li>
              <a 
                href="#demo"
                className={`relative py-2 transition-all duration-300 group ${activeAnchor === 'demo' ? 'text-white' : 'hover:text-white'}`}
                onClick={handleScroll}
              >
                Demo
                <span className={`absolute bottom-0 left-0 h-0.5 bg-gradient-to-r from-purple-500 to-cyan-500 transition-all duration-300 ${activeAnchor === 'demo' ? 'w-full' : 'w-0 group-hover:w-full'}`}></span>
              </a>
            </li>
            <li>
              <a 
                href="#installation"
                className={`relative py-2 transition-all duration-300 group ${activeAnchor === 'installation' ? 'text-white' : 'hover:text-white'}`}
                onClick={handleScroll}
              >
                Installation
                <span className={`absolute bottom-0 left-0 h-0.5 bg-gradient-to-r from-purple-500 to-cyan-500 transition-all duration-300 ${activeAnchor === 'installation' ? 'w-full' : 'w-0 group-hover:w-full'}`}></span>
              </a>
            </li>
          </ul>
        )}

        {/* Right: Actions */}
        <div className="flex items-center gap-2 md:gap-4 shrink-0">
          {isLandingPage ? (
            <>
              <a
                href="https://github.com/CodeGraphContext/CodeGraphContext"
                target="_blank"
                rel="noopener noreferrer"
                className="p-2 hidden sm:flex text-gray-400 hover:text-white transition-all duration-300 hover:scale-110 hover:drop-shadow-[0_0_8px_rgba(168,85,247,0.3)]"
                title="View GitHub Repository"
              >
                <Github className="w-4 h-4" />
              </a>
              <Link to="/explore">
                <MagneticButton className="bg-gradient-to-r from-purple-600 to-cyan-500 hover:from-purple-500 hover:to-cyan-400 text-white shadow-[0_0_15px_rgba(168,85,247,0.3)] hover:shadow-[0_0_25px_rgba(168,85,247,0.5)] font-bold text-[10px] uppercase tracking-widest px-4 py-2 sm:px-6 sm:py-2.5 rounded-full flex items-center gap-2 transition-all duration-300 hover:scale-105">
                  <span className="hidden sm:inline">Launch Explorer</span>
                  <span className="sm:hidden">Explore</span>
                  <Sparkles className="w-3 h-3 transition-transform duration-300 group-hover:rotate-12" />
                </MagneticButton>
              </Link>
            </>
          ) : (
            <Link to="/">
              <MagneticButton className="border border-white/20 hover:border-purple-400/70 bg-transparent hover:bg-purple-500/15 text-white font-bold text-[10px] uppercase tracking-widest px-4 py-2 sm:px-6 sm:py-2.5 rounded-full flex items-center gap-2 transition-all duration-300 hover:scale-105 hover:shadow-[0_0_15px_rgba(168,85,247,0.2)]">
                <ArrowLeft className="w-3 h-3 transition-transform duration-300 group-hover:-translate-x-1" /> Back
              </MagneticButton>
            </Link>
          )}

          {/* Hamburger Menu Icon (Mobile Only) */}
          {isLandingPage && (
            <button
              onClick={() => setIsOpen(!isOpen)}
              className="lg:hidden p-2 text-gray-400 hover:text-white transition-all duration-300 shrink-0 hover:scale-110"
              title="Menu"
            >
              {isOpen ? <X className="w-5 h-5 transition-transform duration-300 rotate-90" /> : <Menu className="w-5 h-5 transition-transform duration-300" />}
            </button>
          )}
        </div>
      </div>

      {/* Mobile Menu Dropdown Panel */}
      {isOpen && isLandingPage && (
        <div className="lg:hidden w-full border-b border-white/10 animate-in fade-in slide-in-from-top-2 duration-300 absolute top-[100%] left-0" style={{ background: 'rgba(0, 0, 0, 0.75)', backdropFilter: 'blur(8px)' }}>
          <ul className="flex flex-col text-[10px] font-bold uppercase tracking-widest text-gray-400 p-4 divide-y divide-white/10">
            {[
              { label: "Features", href: "#features" },
              { label: "Pre-indexed Bundles", href: "#bundle-registry" },
              { label: "Cookbook / Guides", href: "#cookbook" },
              { label: "Interactive Demo", href: "#demo" },
              { label: "Get Started / Install", href: "#installation" },
            ].map((link) => (
              <li key={link.label}>
                <a
                  href={link.href}
                  className={`block py-4 transition-all duration-300 ${activeAnchor === link.href.replace('#', '') ? 'text-white pl-2 border-l border-purple-500' : 'hover:text-white hover:pl-2'}`}
                  onClick={(e) => {
                    setIsOpen(false);
                    handleScroll(e);
                  }}
                >
                  {link.label}
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}
    </nav>
  );
};

export default Navbar;
