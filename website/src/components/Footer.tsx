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
const supabase =
  supabaseUrl && supabaseAnonKey ? getSupabaseClient() : null;

const Footer = () => {
  const [email, setEmail] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [version, setVersion] = useState("");
  useEffect(() => {
    async function fetchVersion() {
      try {
        const res = await fetch(
          "https://raw.githubusercontent.com/CodeGraphContext/CodeGraphContext/main/README.md"
        );
        if (!res.ok) throw new Error("Failed to fetch README");

        const text = await res.text();
        const match = text.match(
          /\*\*Version:\*\*\s*([0-9]+\.[0-9]+\.[0-9]+)/i
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

    // Check if Supabase is configured
    if (!supabase) {
      toast.error(
        "Newsletter subscription is currently unavailable. Please try again later."
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
          // Duplicate email
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
      <SectionDivider variant="wave" className="absolute top-0 left-0 right-0 z-0 opacity-40 rotate-180" />
      <div className="absolute inset-0 opacity-20 pointer-events-none">
        <ParticleBackground />
      </div>
      <div className="container mx-auto max-w-7xl relative z-10 pt-12">
        {/* Top Section */}
        <div className="flex flex-col lg:flex-row justify-between gap-12">
          {/* Left Side: Brand + Resources (closer together) */}
          <div className="flex-1 flex flex-col sm:flex-row gap-12">
            {/* Brand */}
            <div className="flex-1">
              <div className="flex items-center gap-3 mb-4 select-none">
                <img
                  src="/cgcIcon.png"
                  className="w-10 h-10"
                  alt="CodeGraphContext Logo"
                />
                <h3 className="text-2xl font-black text-white uppercase tracking-widest">
                  CodeGraphContext
                </h3>
              </div>
              <p className="text-[10px] font-mono text-gray-500 uppercase tracking-widest mb-6 leading-relaxed max-w-sm">
                Transform your codebase into an intelligent knowledge graph for
                AI assistants.
              </p>
              <div className="flex gap-3 flex-wrap">
                <Button
                  variant="outline"
                  size="sm"
                  asChild
                  className="rounded-full bg-transparent border-white/20 text-white hover:bg-purple-600 hover:text-white shadow-[0_0_15px_rgba(168,85,247,0.4)] transition-colors"
                >
                  <a
                    href="https://github.com/CodeGraphContext/CodeGraphContext"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center"
                  >
                    <FaGithub
                      className="h-4 w-4 mr-2"
                    />
                    <span className="text-[10px] font-black uppercase tracking-widest">GitHub</span>
                  </a>
                </Button>

                <Button
                  variant="outline"
                  size="sm"
                  asChild
                  className="rounded-full bg-transparent border-white/20 text-white hover:bg-purple-600 hover:text-white shadow-[0_0_15px_rgba(168,85,247,0.4)] transition-colors"
                >
                  <a
                    href="https://discord.com/invite/dR4QY32uYQ"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center"
                  >
                    <FaDiscord
                      className="h-4 w-4 mr-2"
                    />
                    <span className="text-[10px] font-black uppercase tracking-widest">Discord</span>
                  </a>
                </Button>

                <Button
                  variant="outline"
                  size="sm"
                  asChild
                  className="rounded-full bg-transparent border-white/20 text-white hover:bg-purple-600 hover:text-white shadow-[0_0_15px_rgba(168,85,247,0.4)] transition-colors"
                >
                  <a
                    href="https://pypi.org/project/codegraphcontext/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center"
                  >
                    <SiPypi
                      className="h-4 w-4 mr-2"
                    />
                    <span className="text-[10px] font-black uppercase tracking-widest">PyPI</span>
                  </a>
                </Button>

                <Button
                  variant="outline"
                  size="sm"
                  asChild
                  className="rounded-full bg-transparent border-white/20 text-white hover:bg-purple-600 hover:text-white shadow-[0_0_15px_rgba(168,85,247,0.4)] transition-colors"
                >
                  <a
                    href="https://codegraphcontext.github.io/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center"
                  >
                    <FiBookOpen
                      className="h-4 w-4 mr-2"
                    />
                    <span className="text-[10px] font-black uppercase tracking-widest">Docs</span>
                  </a>
                </Button>
              </div>
            </div>

            {/* Resources */}
            <div className="w-48">
              <h4 className="text-[11px] font-black uppercase tracking-widest text-white mb-4">Resources</h4>
              <ul className="space-y-3 text-[10px] font-mono uppercase tracking-widest text-gray-500">
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
          </div>

          {/* Right Side: Contact + Newsletter */}
          <div className="flex-1 flex flex-col sm:flex-row gap-12">
            {/* Contact */}
            <div className="w-full sm:w-64 lg:w-72">
              <h4 className="text-[11px] font-black uppercase tracking-widest text-white mb-4">Contact</h4>
              <div className="space-y-5 text-[10px] font-mono text-gray-500 uppercase tracking-widest">
                <div className="flex items-center gap-3">
                  <Mail className="h-4 w-4 shrink-0 text-primary" />
                  <a
                    href="mailto:shashankshekharsingh1205@gmail.com"
                    className="hover:text-white transition-colors text-[9px] whitespace-nowrap"
                  >
                    shashankshekharsingh1205@gmail.com
                  </a>
                </div>
                {/* <div className="flex items-start gap-3">
                  <Phone className="h-5 w-5 mt-1 text-primary" />
                  <a
                    href="tel:+911234567890"
                    className="hover:text-foreground transition-smooth text-sm"
                  >
                    +91 12345 67890
                  </a>
                </div> */}
                <div className="flex items-start gap-3">
                  <MapPin className="h-4 w-4 mt-1 text-primary" />
                  <p>(Available Worldwide 🌍)</p>
                </div>
                <div>
                  <p className="font-black text-white mb-1">
                    Shashank Shekhar Singh
                  </p>
                  <p>Creator & Maintainer</p>
                </div>
              </div>
            </div>

            {/* Newsletter */}
            <div className="flex-1">
              <GlassCard glowColor="none" className="p-6">
                <h4 className="text-[11px] font-black uppercase tracking-widest text-white mb-4">Newsletter</h4>
                <p className="text-[10px] font-mono text-gray-500 uppercase tracking-widest mb-4 leading-relaxed">
                  Stay updated with the latest features, releases, and code
                  intelligence insights.
                </p>
                <form onSubmit={handleNewsletterSubmit} className="space-y-3">
                <div className="flex flex-col sm:flex-row gap-2">
                  <input
                    type="email"
                    placeholder="ENTER YOUR EMAIL"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    disabled={isLoading}
                    className="flex-1 px-4 py-2.5 text-[10px] font-mono border border-white/20 rounded-full bg-black text-white focus:outline-none focus:border-white transition-colors disabled:opacity-50 uppercase tracking-widest placeholder:text-gray-600"
                    required
                  />
                  <Button
                    type="submit"
                    size="sm"
                    disabled={isLoading}
                    className="whitespace-nowrap bg-gradient-to-r from-purple-600 to-cyan-500 hover:opacity-90 text-white shadow-[0_0_15px_rgba(168,85,247,0.3)] transition-all rounded-full font-black text-[10px] uppercase tracking-widest px-6 border-0"
                  >
                    {isLoading ? "SUBSCRIBING..." : "SUBSCRIBE"}
                  </Button>
                </div>
                <p className="text-[8px] font-mono text-gray-600 mt-3 uppercase tracking-widest">
                  No spam. Unsubscribe at any time.
                </p>
                </form>
              </GlassCard>
            </div>
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="border-t border-white/10 mt-12 pt-8 flex flex-col md:flex-row justify-between items-center gap-4 text-[10px] font-mono text-gray-500 uppercase tracking-widest">
          <p>
            © 2026 CodeGraphContext. Released under the MIT License.
          </p>
          <div className="flex items-center gap-4">
            <span>Version {version}</span>
            <div className="w-1 h-1 bg-white/20 rounded-full" />
            <span>Python 3.10+</span>
            <div className="w-1 h-1 bg-white/20 rounded-full" />
            <span>Falkordb or Neo4j</span>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;

