import { Button } from "@/components/ui/button";
import { Mail, MapPin, Phone } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { getSupabaseClient } from "@/lib/supabase-client";
import { FaGithub, FaDiscord } from "react-icons/fa";
import { SiPypi } from "react-icons/si";
import { FiBookOpen } from "react-icons/fi";
import GlassCard from "./GlassCard";
import SectionDivider from "./SectionDivider";
import ParticleBackground from "./ParticleBackground";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;
const supabase = supabaseUrl && supabaseAnonKey ? getSupabaseClient() : null;

const Footer = () => {
  const [email, setEmail] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [version, setVersion] = useState("");

  useEffect(() => {
    async function fetchVersion() {
      try {
        const res = await fetch(
          "https://raw.githubusercontent.com/CodeGraphContext/CodeGraphContext/main/README.md",
        );
        if (!res.ok) throw new Error("Failed to fetch README");
        const text = await res.text();
        const match = text.match(
          /\*\*Version:\*\*\s*([0-9]+\.[0-9]+\.[0-9]+)/i,
        );
        setVersion(match ? match[1] : "N/A");
      } catch (err) {
        console.error(err);
        setVersion("N/A");
      }
    }
    fetchVersion();
  }, []);

  const handleNewsletterSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) {
      toast.error("Please enter your email address");
      return;
    }
    if (!/\S+@\S+\.\S+/.test(email)) {
      toast.error("Please enter a valid email address");
      return;
    }
    if (!supabase) {
      toast.error(
        "Newsletter subscription is currently unavailable. Please try again later.",
      );
      return;
    }
    setIsLoading(true);
    try {
      const { data, error } = await supabase
        .from("subscribers")
        .insert([{ email }]);
      if (error) {
        if (error.code === "23505") {
          toast("You are already subscribed!");
        } else {
          toast.error(error.message);
        }
      } else {
        toast.success("Thank you for subscribing to our newsletter!");
        setEmail("");
      }
    } catch (err) {
      console.error(err);
      toast.error("Failed to subscribe. Please try again later.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <footer className="py-16 px-6 bg-black relative overflow-hidden">
      <SectionDivider
        variant="wave"
        className="absolute top-0 left-0 right-0 z-0 opacity-40 rotate-180"
      />
      <div className="absolute inset-0 opacity-20 pointer-events-none">
        <ParticleBackground />
      </div>

      <div className="container mx-auto max-w-7xl relative z-10">
        {/* Top Section - Balanced Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-12 gap-10 lg:gap-8">
          {/* Brand + Social */}
          <div className="lg:col-span-5 flex flex-col">
            <div className="flex items-center gap-3 mb-6 select-none">
              <img
                src="/cgcIcon.png"
                className="w-10 h-10"
                alt="CodeGraphContext Logo"
              />
              <h3 className="text-2xl font-black text-white uppercase tracking-widest">
                CodeGraphContext
              </h3>
            </div>

            <p className="text-sm text-gray-400 leading-relaxed mb-8 max-w-md">
              Transform your codebase into an intelligent knowledge graph for AI
              assistants.
            </p>

            {/* Social Links - Compact */}
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                size="sm"
                asChild
                className="rounded-full bg-transparent border-white/30 text-white hover:bg-white/10 hover:border-white/50 text-xs h-9 px-4 transition-all"
              >
                <a
                  href="https://github.com/CodeGraphContext/CodeGraphContext"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2"
                >
                  <FaGithub className="h-4 w-4" />
                  GitHub
                </a>
              </Button>
              <Button
                variant="outline"
                size="sm"
                asChild
                className="rounded-full bg-transparent border-white/30 text-white hover:bg-white/10 hover:border-white/50 text-xs h-9 px-4 transition-all"
              >
                <a
                  href="https://discord.com/invite/dR4QY32uYQ"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2"
                >
                  <FaDiscord className="h-4 w-4" />
                  Discord
                </a>
              </Button>
              <Button
                variant="outline"
                size="sm"
                asChild
                className="rounded-full bg-transparent border-white/30 text-white hover:bg-white/10 hover:border-white/50 text-xs h-9 px-4 transition-all"
              >
                <a
                  href="https://pypi.org/project/codegraphcontext/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2"
                >
                  <SiPypi className="h-4 w-4" />
                  PyPI
                </a>
              </Button>
              <Button
                variant="outline"
                size="sm"
                asChild
                className="rounded-full bg-transparent border-white/30 text-white hover:bg-white/10 hover:border-white/50 text-xs h-9 px-4 transition-all"
              >
                <a
                  href="https://codegraphcontext.github.io/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2"
                >
                  <FiBookOpen className="h-4 w-4" />
                  Docs
                </a>
              </Button>
            </div>
          </div>

          {/* Resources */}
          <div className="lg:col-span-3">
            <h4 className="text-xs font-bold uppercase tracking-widest text-white mb-6">
              Resources
            </h4>
            <ul className="space-y-3 text-sm text-gray-400">
              <li>
                <a
                  href="https://codegraphcontext.github.io/"
                  className="hover:text-white transition-colors"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Documentation
                </a>
              </li>
              <li>
                <a
                  href="https://github.com/CodeGraphContext/CodeGraphContext/blob/main/docs/docs/cookbook.md"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hover:text-white transition-colors"
                >
                  Cookbook
                </a>
              </li>
              <li>
                <a
                  href="https://github.com/CodeGraphContext/CodeGraphContext/blob/main/CONTRIBUTING.md"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hover:text-white transition-colors"
                >
                  Contributing
                </a>
              </li>
              <li>
                <a
                  href="https://github.com/CodeGraphContext/CodeGraphContext/issues"
                  className="hover:text-white transition-colors"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Issues
                </a>
              </li>
            </ul>
          </div>

          {/* Contact */}
          <div className="lg:col-span-4">
            <h4 className="text-xs font-bold uppercase tracking-widest text-white mb-6">
              Contact
            </h4>
            <div className="space-y-6 text-sm text-gray-400">
              <div className="flex items-start gap-3">
                <Mail className="h-4 w-4 mt-1 text-purple-400 flex-shrink-0" />
                <a
                  href="mailto:shashankshekharsingh1205@gmail.com"
                  className="hover:text-white transition-colors break-all"
                >
                  shashankshekharsingh1205@gmail.com
                </a>
              </div>
              <div className="flex items-start gap-3">
                <MapPin className="h-4 w-4 mt-1 text-purple-400 flex-shrink-0" />
                <p>Available Worldwide 🌍</p>
              </div>

              <div className="pt-4 border-t border-white/10">
                <p className="font-semibold text-white">
                  Shashank Shekhar Singh
                </p>
                <p className="text-gray-500 text-xs">
                  Creator &amp; Maintainer
                </p>
              </div>
            </div>
          </div>

          {/* Newsletter - Compact */}
          <div className="lg:col-span-5 lg:col-start-8">
            <GlassCard glowColor="none" className="p-6 h-full">
              <h4 className="text-xs font-bold uppercase tracking-widest text-white mb-3">
                Newsletter
              </h4>
              <p className="text-sm text-gray-400 mb-6 leading-relaxed">
                Stay updated with the latest features, releases, and code
                intelligence insights.
              </p>

              <form onSubmit={handleNewsletterSubmit} className="space-y-4">
                <div className="flex flex-col sm:flex-row gap-3">
                  <input
                    type="email"
                    placeholder="YOUR EMAIL"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    disabled={isLoading}
                    className="flex-1 px-5 py-3 text-sm font-mono border border-white/20 rounded-full bg-black/70 text-white focus:outline-none focus:border-purple-400 transition-colors disabled:opacity-50 placeholder:text-gray-600"
                    required
                  />
                  <Button
                    type="submit"
                    size="sm"
                    disabled={isLoading}
                    className="whitespace-nowrap bg-gradient-to-r from-purple-600 to-cyan-500 hover:brightness-110 text-white font-bold text-sm uppercase tracking-widest px-8 py-3 rounded-full border-0 transition-all min-w-[140px]"
                  >
                    {isLoading ? "SUBSCRIBING..." : "SUBSCRIBE"}
                  </Button>
                </div>
                <p className="text-[10px] text-gray-500 font-mono">
                  No spam. Unsubscribe at any time.
                </p>
              </form>
            </GlassCard>
          </div>
        </div>

        {/* Bottom Bar - Centered & Cohesive */}
        <div className="border-t border-white/10 mt-16 pt-8">
          <div className="flex flex-col md:flex-row justify-between items-center gap-6 text-xs text-gray-500 font-mono tracking-widest">
            <p>© 2026 CodeGraphContext. Released under the MIT License.</p>

            <div className="flex items-center gap-6 text-center md:text-left">
              <span>Version {version}</span>
              <span className="hidden md:inline">•</span>
              <span>Python 3.10+</span>
              <span className="hidden md:inline">•</span>
              <span>Falkordb or Neo4j</span>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
