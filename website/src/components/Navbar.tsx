import React, { useEffect, useMemo, useState } from "react";
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
  const [isScrolled, setIsScrolled] = useState(false);
  const [activeSection, setActiveSection] = useState("hero");

  const navItems = useMemo(
    () => [
      { label: "Features", href: "#features", id: "features" },
      { label: "Pre-indexed", href: "#bundle-registry", id: "bundle-registry" },
      { label: "Cookbook", href: "#cookbook", id: "cookbook" },
      { label: "Demo", href: "#demo", id: "demo" },
      { label: "Installation", href: "#installation", id: "installation" },
    ],
    []
  );

  useEffect(() => {
    const onScroll = () => {
      setIsScrolled(window.scrollY > 12);

      if (!isLandingPage) return;

      const sectionIds = navItems.map((item) => item.id);
      const closest = sectionIds
        .map((id) => {
          const el = document.getElementById(id);
          if (!el) return null;
          const rect = el.getBoundingClientRect();
          return { id, distance: Math.abs(rect.top - 120) };
        })
        .filter(Boolean)
        .sort((a, b) => (a!.distance - b!.distance))[0];

      if (closest) setActiveSection(closest.id);
    };

    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [isLandingPage, navItems, location.pathname, location.hash]);

  useEffect(() => {
    if (!location.hash) return;
    const next = location.hash.replace("#", "");
    if (next) setActiveSection(next);
  }, [location.hash]);

  return (
    <nav
      className={`fixed top-0 left-0 z-50 w-full select-none border-b transition-all duration-300 ${
        isScrolled
          ? "border-white/15 bg-black/70 shadow-[0_8px_40px_rgba(0,0,0,0.35)] backdrop-blur-xl"
          : "border-white/5 bg-black/35 backdrop-blur-md"
      }`}
    >
      <div className="mx-auto flex h-14 w-full max-w-7xl items-center justify-between px-4 md:h-16 md:px-6">
        
        {/* Left: Brand Logo & Title */}
        <Link
          to="/"
          className="group mr-4 flex shrink-0 items-center gap-2 md:gap-3"
        >
          <img
            src="/cgcIcon.png"
            className="h-7 w-7 transition-transform duration-300 group-hover:scale-95 md:h-8 md:w-8"
            alt="CodeGraphContext Logo"
          />
          <span className="block text-sm font-black uppercase tracking-tighter text-white transition-colors duration-300 group-hover:text-purple-200 md:text-lg">
            CodeGraphContext
          </span>
        </Link>

        {/* Center: Anchors (Only displayed on landing page for optimal UX) */}
        {isLandingPage && (
          <ul className="hidden items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-2 py-1.5 text-[10px] font-bold uppercase tracking-[0.28em] text-gray-400 lg:flex">
            <li>
              <a
                href="#features"
                className={`rounded-full px-3 py-2 transition-all duration-300 hover:text-white ${
                  activeSection === "features" ? "bg-white/10 text-white shadow-[0_0_20px_rgba(168,85,247,0.15)]" : "text-gray-400"
                }`}
                onClick={handleScroll}
              >
                Features
              </a>
            </li>
            <li>
              <a
                href="#bundle-registry"
                className={`rounded-full px-3 py-2 transition-all duration-300 hover:text-white ${
                  activeSection === "bundle-registry" ? "bg-white/10 text-white shadow-[0_0_20px_rgba(168,85,247,0.15)]" : "text-gray-400"
                }`}
                onClick={handleScroll}
              >
                Pre-indexed
              </a>
            </li>
            <li>
              <a
                href="#cookbook"
                className={`rounded-full px-3 py-2 transition-all duration-300 hover:text-white ${
                  activeSection === "cookbook" ? "bg-white/10 text-white shadow-[0_0_20px_rgba(168,85,247,0.15)]" : "text-gray-400"
                }`}
                onClick={handleScroll}
              >
                Cookbook
              </a>
            </li>
            <li>
              <a
                href="#demo"
                className={`rounded-full px-3 py-2 transition-all duration-300 hover:text-white ${
                  activeSection === "demo" ? "bg-white/10 text-white shadow-[0_0_20px_rgba(168,85,247,0.15)]" : "text-gray-400"
                }`}
                onClick={handleScroll}
              >
                Demo
              </a>
            </li>
            <li>
              <a
                href="#installation"
                className={`rounded-full px-3 py-2 transition-all duration-300 hover:text-white ${
                  activeSection === "installation" ? "bg-white/10 text-white shadow-[0_0_20px_rgba(168,85,247,0.15)]" : "text-gray-400"
                }`}
                onClick={handleScroll}
              >
                Installation
              </a>
            </li>
          </ul>
        )}

        {/* Right: Actions */}
        <div className="flex shrink-0 items-center gap-2 md:gap-4">
          {isLandingPage ? (
            <>
              <a
                href="https://github.com/CodeGraphContext/CodeGraphContext"
                target="_blank"
                rel="noopener noreferrer"
                className="hidden rounded-full border border-white/10 bg-white/[0.03] p-2 text-gray-400 transition-all duration-300 hover:border-white/20 hover:bg-white/10 hover:text-white sm:flex"
                title="View GitHub Repository"
              >
                <Github className="w-4 h-4" />
              </a>
              <Link to="/explore">
                <MagneticButton className="flex items-center gap-2 rounded-full border border-purple-400/30 bg-gradient-to-r from-purple-600 to-cyan-500 px-4 py-2 text-[10px] font-bold uppercase tracking-[0.28em] text-white shadow-[0_0_18px_rgba(168,85,247,0.28)] transition-all duration-300 hover:opacity-95 sm:px-6 sm:py-2.5">
                  <span className="hidden sm:inline">Launch Explorer</span>
                  <span className="sm:hidden">Explore</span>
                  <Sparkles className="w-3 h-3" />
                </MagneticButton>
              </Link>
            </>
          ) : (
            <Link to="/">
              <MagneticButton className="flex items-center gap-2 rounded-full border border-white/20 bg-transparent px-4 py-2 text-[10px] font-bold uppercase tracking-[0.28em] text-white transition-all duration-300 hover:border-purple-500/50 hover:bg-purple-500/10 sm:px-6 sm:py-2.5">
                <ArrowLeft className="w-3 h-3" /> Back
              </MagneticButton>
            </Link>
          )}

          {/* Hamburger Menu Icon (Mobile Only) */}
          {isLandingPage && (
            <button
              onClick={() => setIsOpen(!isOpen)}
              className="shrink-0 rounded-full border border-white/10 bg-white/[0.03] p-2 text-gray-400 transition-all duration-300 hover:border-white/20 hover:bg-white/10 hover:text-white lg:hidden"
              title="Menu"
            >
              {isOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          )}
        </div>
      </div>

      {/* Mobile Menu Dropdown Panel */}
      {isOpen && isLandingPage && (
        <div className="absolute left-0 top-[100%] w-full border-b border-white/10 bg-black/90 backdrop-blur-xl lg:hidden">
          <ul className="flex flex-col divide-y divide-white/10 p-4 text-[10px] font-bold uppercase tracking-[0.28em] text-gray-400">
            {navItems.map((link) => (
              <li key={link.label}>
                <a
                  href={link.href}
                  className={`block rounded-2xl px-4 py-4 transition-all duration-300 hover:bg-white/5 hover:text-white ${
                    activeSection === link.id ? "bg-white/5 text-white" : ""
                  }`}
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
