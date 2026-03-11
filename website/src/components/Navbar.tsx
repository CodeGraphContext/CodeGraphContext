import React, { useState } from "react";
import { Menu, X } from "lucide-react";
import { Link } from "react-router-dom";

function handleScroll(e: React.MouseEvent<HTMLAnchorElement>, callback?: () => void) {
  const href = e.currentTarget.getAttribute('href');
  if (href && href.startsWith('#')) {
    e.preventDefault();
    const id = href.replace('#', '');
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      if (callback) callback();
    }
  }
}

const Navbar: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);

  const navLinks = [
    { href: "#features", label: "Features" },
    { href: "#bundle-registry", label: "Pre-indexed Repositories" },
    { href: "#bundle-generator", label: "Generate Bundle" },
    { href: "#cookbook", label: "Cookbook" },
    { href: "#demo", label: "Demo" },
    { href: "#installation", label: "Installation" },
    { href: "#testimonials", label: "Testimonials" },
  ];

  return (
    <nav className="fixed top-3 md:top-6 left-1/2 transform -translate-x-1/2 z-50 w-[94vw] max-w-6xl">
      <div
        className={`rounded-2xl md:rounded-full backdrop-blur-2xl shadow-md border px-4 md:px-8 py-2 md:py-3 transition-colors duration-300 border-gray-300 dark:border-white/20 ${
          isOpen ? "rounded-2xl" : "md:rounded-full"
        }`}
        style={{
          background: 'linear-gradient(to bottom, hsl(var(--card) / 0.8), hsl(var(--graph-node-1) / 0.45))',
        }}
      >
        <div className="flex items-center justify-between md:justify-center">
          {/* Mobile Logo/Title (Optional, adding for better context in mobile menu) */}
          <Link to="/" className="md:hidden font-bold text-xs bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent hover:opacity-80 transition-opacity">
            CodeGraphContext
          </Link>

          {/* Desktop Menu */}
          <ul className="hidden md:flex flex-wrap justify-center gap-2 md:gap-4 font-semibold text-sm md:text-base text-[hsl(var(--foreground))]">
            {navLinks.map((link) => (
              <li key={link.href}>
                <a
                  href={link.href}
                  className="px-2 py-1 md:px-4 md:py-2 rounded-full hover:bg-[hsl(var(--primary)/0.15)] hover:text-[hsl(var(--primary))] transition"
                  onClick={handleScroll}
                >
                  {link.label}
                </a>
              </li>
            ))}
          </ul>

          {/* Mobile Toggle Icon */}
          <button
            className="md:hidden p-2 text-[hsl(var(--foreground))] hover:text-[hsl(var(--primary))] transition-colors"
            onClick={() => setIsOpen(!isOpen)}
            aria-label="Toggle menu"
          >
            {isOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
        </div>

        {/* Mobile Menu Content */}
        {isOpen && (
          <ul className="md:hidden flex flex-col gap-2 mt-4 pb-4 font-semibold text-sm text-[hsl(var(--foreground))] animate-in fade-in slide-in-from-top-4 duration-200">
            {navLinks.map((link) => (
              <li key={link.href} className="w-full">
                <a
                  href={link.href}
                  className="block px-4 py-3 rounded-xl hover:bg-[hsl(var(--primary)/0.15)] hover:text-[hsl(var(--primary))] transition text-center"
                  onClick={(e) => handleScroll(e, () => setIsOpen(false))}
                >
                  {link.label}
                </a>
              </li>
            ))}
          </ul>
        )}
      </div>
    </nav>
  );
};

export default Navbar;
