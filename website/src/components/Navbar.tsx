import React, { useState, useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { Sparkles, ArrowLeft, Github, Menu, X } from "lucide-react";
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
  const [activeSection, setActiveSection] = useState("");

  // Scroll spy to monitor visibility changes
  useEffect(() => {
    if (!isLandingPage) return;

    const sections = ["features", "bundle-registry", "cookbook", "demo", "installation"];
    
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          // Lowered threshold to 0.2 so it registers even if a section partially occupies the screen
          if (entry.isIntersecting && entry.intersectionRatio >= 0.2) {
            setActiveSection(entry.target.id);
          }
        });
      },
      { threshold: [0.2, 0.5], rootMargin: "-10% 0px -70% 0px" }
    );

    sections.forEach((id) => {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    });

    return () => observer.disconnect();
  }, [isLandingPage]);

  // Scroll progress for the indicator strip under the navbar edge
  const [scrollProgress, setScrollProgress] = useState(0);

  useEffect(() => {
    const updateProgress = () => {
      const scrollTop = window.scrollY;
      const scrollableDistance =
        document.documentElement.scrollHeight - window.innerHeight;
      const progress =
        scrollableDistance > 0
          ? Math.min(Math.max((scrollTop / scrollableDistance) * 100, 0), 100)
          : 0;
      setScrollProgress(progress);
    };

    window.addEventListener("scroll", updateProgress, { passive: true });
    updateProgress();
    return () => window.removeEventListener("scroll", updateProgress);
  }, []);

  return (
    <nav className="fixed top-0 left-0 z-50 w-full select-none bg-black border-b border-white/10">
      {/* Scroll Progress Indicator */}
      <div className="h-0.5 w-full bg-zinc-900 overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-purple-600 via-cyan-500 to-purple-600 transition-all duration-200 ease-out"
          style={{ width: `${scrollProgress}%` }}
        />
      </div>

      <div className="w-full max-w-7xl mx-auto px-4 md:px-6 h-14 md:h-16 flex items-center justify-between">
        
        {/* Left: Brand Logo & Title */}
        <Link to="/" className="flex items-center gap-2 md:gap-3 mr-4 shrink-0 group">
          <img
            src="/cgcIcon.png"
            className="w-7 h-7 md:w-8 md:h-8 hover:scale-95 transition-transform duration-300"
            alt="CodeGraphContext Logo"
          />
          <span className="font-black text-sm md:text-lg gradient-text tracking-tighter uppercase block">
            CodeGraphContext
          </span>
        </Link>

        {/* Center: Anchors */}
        {isLandingPage && (
          <ul className="hidden lg:flex items-center gap-6 font-bold text-[10px] uppercase tracking-widest text-gray-500">
            {[
              { label: "Features", href: "#features" },
              { label: "Understand", href: "/understand", isRoute: true },
              { label: "Pre-indexed", href: "#bundle-registry" },
              { label: "Cookbook", href: "#cookbook" },
              { label: "Demo", href: "#demo" },
              { label: "Installation", href: "#installation" },
            ].map((link) => {
              const isRoute = (link as any).isRoute;
              const id = link.href.replace("#", "");
              const isActive = isRoute
                ? location.pathname === link.href
                : activeSection === id;
              
              return (
                <li key={link.label} className="relative flex items-center h-full py-4">
                  {isRoute ? (
                    <Link
                      to={link.href}
                      className={`transition-colors duration-200 relative pb-1 ${isActive ? "text-white" : "hover:text-white text-gray-500"}`}
                    >
                      {link.label}
                      {isActive && (
                        <span className="absolute bottom-0 left-0 w-full h-[2px] bg-purple-500 transition-all duration-300" />
                      )}
                    </Link>
                  ) : (
                    <a
                      href={link.href}
                      className={`transition-colors duration-200 relative pb-1 ${isActive ? "text-white" : "hover:text-white text-gray-500"}`}
                      onClick={(e) => {
                        setActiveSection(id);
                        handleScroll(e);
                      }}
                    >
                      {link.label}
                      {isActive && (
                        <span className="absolute bottom-0 left-0 w-full h-[2px] bg-purple-500 transition-all duration-300" />
                      )}
                    </a>
                  )}
                </li>
              );
            })}
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
                className="p-2 hidden sm:flex text-gray-500 hover:text-white transition-colors duration-200"
                title="View GitHub Repository"
              >
                <Github className="w-4 h-4" />
              </a>
              <Link to="/explore">
                <MagneticButton className="bg-gradient-to-r from-purple-600 to-cyan-500 hover:opacity-90 text-white shadow-[0_0_15px_rgba(168,85,247,0.3)] font-bold text-[10px] uppercase tracking-widest px-4 py-2 sm:px-6 sm:py-2.5 rounded-full flex items-center gap-2 transition-all duration-300">
                  <span className="hidden sm:inline">Launch Explorer</span>
                  <span className="sm:hidden">Explore</span>
                  <Sparkles className="w-3 h-3" />
                </MagneticButton>
              </Link>
            </>
          ) : (
            <Link to="/">
              <MagneticButton className="border border-white/20 hover:border-purple-500/50 bg-transparent hover:bg-purple-500/10 text-white font-bold text-[10px] uppercase tracking-widest px-4 py-2 sm:px-6 sm:py-2.5 rounded-full flex items-center gap-2 transition-colors duration-300">
                <ArrowLeft className="w-3 h-3" /> Back
              </MagneticButton>
            </Link>
          )}

          {/* Hamburger Menu Icon (Mobile Only) */}
          {isLandingPage && (
            <button
              onClick={() => setIsOpen(!isOpen)}
              className="lg:hidden p-2 text-gray-500 hover:text-white transition-colors duration-200 shrink-0"
              title="Menu"
            >
              {isOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          )}
        </div>
      </div>

      {/* Mobile Menu Dropdown Panel */}
      {isOpen && isLandingPage && (
        <div className="lg:hidden w-full border-b border-white/10 bg-black absolute top-[100%] left-0">
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
                  className="block py-4 hover:text-white transition-colors duration-200"
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