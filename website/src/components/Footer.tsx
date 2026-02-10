import { Button } from "@/components/ui/button";
import { Github, ExternalLink, Mail, MapPin, Phone } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { createClient } from "@supabase/supabase-js";
import { FaGithub, FaDiscord } from "react-icons/fa";
import { SiPypi } from "react-icons/si";
import { FiBookOpen } from "react-icons/fi";

// Only create Supabase client if environment variables are set
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;
const supabase =
  supabaseUrl && supabaseAnonKey
    ? createClient(supabaseUrl, supabaseAnonKey)
    : null;

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
    <footer className="border-t border-border/50 py-16 px-6 bg-muted/10" data-aos="fade-up">
      <div className="container mx-auto max-w-7xl">
        {/* Top Section */}
        <div className="flex flex-col lg:flex-row justify-between gap-12">
          {/* Left Side: Brand + Resources (closer together) */}
          <div className="flex-1 flex flex-col sm:flex-row gap-12">
            {/* Brand */}
            <div className="flex-1">
              <h3 className="text-2xl font-bold bg-gradient-primary bg-clip-text text-transparent mb-4">
                CodeGraphContext
              </h3>
              <p className="text-muted-foreground mb-6 leading-relaxed max-w-sm">
                Transform your codebase into an intelligent knowledge graph for
                AI assistants.
              </p>
              <div className="flex gap-3 flex-wrap">
                <Button
                  variant="outline"
                  size="sm"
                  asChild
                  className="social-btn social-github social-float"
                >
                  <a
                    href="https://github.com/CodeGraphContext/CodeGraphContext"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center"
                  >
                    <FaGithub
                      className="h-4 w-4 mr-2"
                      style={{ color: "#9CA3AF" }}
                    />
                    <span>GitHub</span>
                  </a>
                </Button>

                <Button
                  variant="outline"
                  size="sm"
                  asChild
                  className="social-btn social-discord social-float"
                >
                  <a
                    href="https://discord.com/invite/dR4QY32uYQ"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center"
                  >
                    <FaDiscord
                      className="h-4 w-4 mr-2"
                      style={{ color: "#5865F2" }}
                    />
                    <span>Discord</span>
                  </a>
                </Button>

                <Button
                  variant="outline"
                  size="sm"
                  asChild
                  className="social-btn social-pypi social-float"
                >
                  <a
                    href="https://pypi.org/project/codegraphcontext/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center"
                  >
                    <SiPypi
                      className="h-4 w-4 mr-2"
                      style={{ color: "#EAB308" }}
                    />
                    <span>PyPI</span>
                  </a>
                </Button>

                <Button
                  variant="outline"
                  size="sm"
                  asChild
                  className="social-btn social-docs social-float"
                >
                  <a
                    href="https://codegraphcontext.github.io/CodeGraphContext/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center"
                  >
                    <FiBookOpen
                      className="h-4 w-4 mr-2"
                      style={{ color: "#6366F1" }}
                    />
                    <span>Documentation</span>
                  </a>
                </Button>
              </div>
            </div>

            {/* Resources */}
            <div className="w-48">
              <h4 className="font-semibold mb-4">Resources</h4>
              <ul className="space-y-3 text-muted-foreground">
                <li>
                  <a
                    href="https://codegraphcontext.github.io/CodeGraphContext/"
                    className="hover:text-foreground transition-smooth"
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
                    className="hover:text-foreground transition-smooth"
                  >
                    Cookbook
                  </a>
                </li>
                <li>
                  <a
                    href="https://github.com/CodeGraphContext/CodeGraphContext/blob/main/CONTRIBUTING.md"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="hover:text-foreground transition-smooth"
                  >
                    Contributing
                  </a>
                </li>
                <li>
                  <a
                    href="https://github.com/CodeGraphContext/CodeGraphContext/issues"
                    className="hover:text-foreground transition-smooth"
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
              <h4 className="font-semibold mb-4">Contact</h4>
              <div className="space-y-5 text-muted-foreground">
                <div className="flex items-center gap-3">
                  <Mail className="h-5 w-5 text-primary shrink-0" />
                  <a
                    href="mailto:shashankshekharsingh1205@gmail.com"
                    className="hover:text-foreground transition-smooth text-sm whitespace-nowrap"
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
                  <MapPin className="h-5 w-5 mt-1 text-primary" />
                  <p className="text-sm">(Available Worldwide 🌍)</p>
                </div>
                <div>
                  <p className="font-medium text-foreground">
                    Shashank Shekhar Singh
                  </p>
                  <p className="text-sm">Creator & Maintainer</p>
                </div>
              </div>
            </div>

            {/* Newsletter */}
            <div className="flex-1">
              <h4 className="font-semibold mb-4">Newsletter</h4>
              <p className="text-muted-foreground mb-4 text-sm leading-relaxed">
                Stay updated with the latest features, releases, and code
                intelligence insights.
              </p>
              <form onSubmit={handleNewsletterSubmit} className="space-y-3">
                <div className="flex flex-col sm:flex-row gap-2">
                  <input
                    type="email"
                    placeholder="Enter your email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    disabled={isLoading}
                    className="flex-1 px-3 py-2 text-sm border border-border rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-smooth disabled:opacity-50"
                    required
                  />
                  <Button
                    type="submit"
                    size="sm"
                    disabled={isLoading}
                    className="whitespace-nowrap"
                  >
                    {isLoading ? "Subscribing..." : "Subscribe"}
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground">
                  No spam. Unsubscribe at any time.
                </p>
              </form>
            </div>
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="border-t border-border/50 mt-12 pt-8 flex flex-col md:flex-row justify-between items-center gap-4">
          <p className="text-muted-foreground text-sm">
            © 2026 CodeGraphContext. Released under the MIT License.
          </p>
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <span>Version {version}</span>
            <div className="w-1 h-1 bg-muted-foreground rounded-full" />
            <span>Python 3.10+</span>
            <div className="w-1 h-1 bg-muted-foreground rounded-full" />
            <span>Falkordb or Neo4j</span>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;

