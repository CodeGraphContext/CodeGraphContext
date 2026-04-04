import React from "react";
import { FaGlobe, FaYoutube, FaMedium, FaTwitter, FaReddit, FaGithub, FaBook, FaBullhorn, FaStackOverflow, FaRegNewspaper } from "react-icons/fa";
// Only import available icons from Si (react-icons/si)
import { SiVercel } from "react-icons/si";


export default function SocialMentionsTimeline() {
  const links = [
    { name: "Website", url: "https://codegraphcontext.vercel.app/", icon: <FaGlobe />, color: "#00B6F0", button: "Check our website" },
    { name: "Youtube", url: "https://www.youtube.com/watch?v=KYYSdxhg1xU", icon: <FaYoutube />, color: "#FF0000", button: "Watch on YouTube" },
    { name: "Blog", url: "https://medium.com/@shashankshekharsingh1205/building-codegraphcontext-my-end-term-journey-in-summer-of-bitcoin-2025-422c9a4dc87e", icon: <FaMedium />, color: "#02B875", button: "Read the blog" },
    { name: "Twitter", url: "https://x.com/braidpool/status/1968683721625637203", icon: <FaTwitter />, color: "#1DA1F2", button: "View on Twitter/X" },
    { name: "PulseMCP", url: "https://www.pulsemcp.com/servers/codegraphcontext", icon: <FaBullhorn />, color: "#6366F1", button: "See on PulseMCP" },
    { name: "MCPMarket", url: "https://mcpmarket.com/server/codegraphcontext", icon: <FaBook />, color: "#6366F1", button: "View on MCPMarket" },
    { name: "Playbooks", url: "https://playbooks.com/mcp/codegraphcontext", icon: <FaBook />, color: "#6366F1", button: "Open Playbook" },
    { name: "MCPHunt", url: "https://mcp-hunt.com/mcp/server/codegraphcontext", icon: <FaRegNewspaper />, color: "#6366F1", button: "See on MCPHunt" },
    { name: "StackerNews", url: "https://stacker.news/items/1227191", icon: <FaStackOverflow />, color: "#F48024", button: "See on StackerNews" },
    { name: "Glama.ai", url: "https://glama.ai/mcp/servers/@CodeGraphContext/CodeGraphContext/blob/a346d340d8f705ce93626b4b322dd0e2823ba46b/src/codegraphcontext/core/jobs.py", icon: <FaGlobe />, color: "#00B6F0", button: "See on Glama.ai" },
    { name: "Github", url: "https://github.com/punkpeye/awesome-mcp-servers?tab=readme-ov-file#coding-agents", icon: <FaGithub />, button: "See on GitHub" },
    { name: "Mcpservers.org", url: "https://mcpservers.org/servers/CodeGraphContext/codegraphcontext", icon: <FaGlobe />, color: "#00B6F0", button: "See on Mcpservers.org" },
    { name: "Skyworks", url: "https://skywork.ai/skypage/en/codegraph-smart-code-companion/1978349276941164544", icon: <SiVercel />, button: "See on Skyworks" },
    { name: "Reddit Announcement", url: "https://www.reddit.com/r/mcp/comments/1o22gc5/i_built_codegraphcontext_an_mcp_server_that/", icon: <FaReddit />, color: "#FF5700", button: "See Reddit post" },
  ];
  return (
    <section className="py-24 px-4 bg-muted" data-aos="fade-in">
      <div className="container mx-auto max-w-5xl">
        <div className="text-center mb-16" data-aos="fade-down">
          <h2 className="text-3xl md:text-4xl font-bold mb-4 bg-gradient-to-r from-primary via-primary to-accent bg-clip-text text-transparent py-2">
            Social Mentions & Recognitions
          </h2>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            CodeGraphContext has been recognized and mentioned across top platforms. Here are some highlights from our journey:
          </p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-6 justify-items-center" data-aos="fade-up">
          {(() => {
            const rows = [];
            const perRow = 3;
            for (let i = 0; i < links.length; i += perRow) {
              const rowLinks = links.slice(i, i + perRow);
              if (rowLinks.length === 2 && i + perRow >= links.length) {
                rows.push(
                  <a
                    key={rowLinks[0].url}
                    href={rowLinks[0].url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block rounded-lg shadow-sm hover:shadow-md transition-shadow p-6 border border-muted bg-card text-card-foreground group w-full border-l-4"
                    style={{ textDecoration: 'none', borderLeftColor: rowLinks[0].color || 'var(--primary)' }}
                  >
                    <div className="flex items-center gap-3 mb-2">
                      <span className={`text-2xl transition-colors ${rowLinks[0].name === "Github" || rowLinks[0].name === "Skyworks"? "text-black dark:text-white": ""}`}style={rowLinks[0].name !== "Github" && rowLinks[0].name !== "Skyworks"? { color: rowLinks[0].color }: {}}>{rowLinks[0].icon}</span>
                      <span className="font-semibold text-lg text-foreground group-hover:text-primary transition-colors">{rowLinks[0].name}</span>
                    </div>
                    <div className="flex justify-center mt-4">
                      <button
                        className="px-4 py-2 rounded-md bg-muted text-foreground font-medium border border-border hover:bg-accent/20 hover:text-primary transition-colors shadow-none"
                        type="button"
                        tabIndex={-1}
                        onClick={e => { e.preventDefault(); window.open(rowLinks[0].url, '_blank', 'noopener,noreferrer'); }}
                      >
                        {rowLinks[0].button}
                      </button>
                    </div>
                  </a>
                );
                rows.push(<div key={`empty-col-center-${i}`} className="hidden md:block" />);
                rows.push(
                  <a
                    key={rowLinks[1].url}
                    href={rowLinks[1].url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block rounded-lg shadow-sm hover:shadow-md transition-shadow p-6 border border-muted bg-card text-card-foreground group w-full border-l-4"
                    style={{ textDecoration: 'none', borderLeftColor: rowLinks[1].color || 'var(--primary)' }}
                  >
                    <div className="flex items-center gap-3 mb-2">
                      <span className={`text-2xl transition-colors ${rowLinks[1].name === "Github" || rowLinks[1].name === "Skyworks"? "text-black dark:text-white": ""}`}style={rowLinks[1].name !== "Github" && rowLinks[1].name !== "Skyworks"? { color: rowLinks[1].color }: {}}>{rowLinks[1].icon}</span>
                      <span className="font-semibold text-lg text-foreground group-hover:text-primary transition-colors">{rowLinks[1].name}</span>
                    </div>
                    <div className="flex justify-center mt-4">
                      <button
                        className="px-4 py-2 rounded-md bg-muted text-foreground font-medium border border-border hover:bg-accent/20 hover:text-primary transition-colors shadow-none"
                        type="button"
                        tabIndex={-1}
                        onClick={e => { e.preventDefault(); window.open(rowLinks[1].url, '_blank', 'noopener,noreferrer'); }}
                      >
                        {rowLinks[1].button}
                      </button>
                    </div>
                  </a>
                );
              } else if (rowLinks.length === 1 && i + perRow >= links.length) {
                rows.push(<div key={`empty-col1-${i}`} className="hidden md:block" />);
                rowLinks.forEach((link) => {
                  rows.push(
                    <a
                      key={link.url}
                      href={link.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block rounded-lg shadow-sm hover:shadow-md transition-shadow p-6 border border-muted bg-card text-card-foreground group w-full border-l-4"
                      style={{ textDecoration: 'none', borderLeftColor: link.color || 'var(--primary)' }}
                    >
                      <div className="flex items-center gap-3 mb-2">
                        <span className={`text-2xl transition-colors ${link.name === "Github" || link.name === "Skyworks"? "text-black dark:text-white": ""}`}style={link.name !== "Github" && link.name !== "Skyworks"? { color: link.color }: {}}>{link.icon}</span>
                        <span className="font-semibold text-lg text-foreground group-hover:text-primary transition-colors">{link.name}</span>
                      </div>
                      <div className="flex justify-center mt-4">
                        <button
                          className="px-4 py-2 rounded-md bg-muted text-foreground font-medium border border-border hover:bg-accent/20 hover:text-primary transition-colors shadow-none"
                          type="button"
                          tabIndex={-1}
                          onClick={e => { e.preventDefault(); window.open(link.url, '_blank', 'noopener,noreferrer'); }}
                        >
                          {link.button}
                        </button>
                      </div>
                    </a>
                  );
                });
                rows.push(<div key={`empty-col2-${i}`} className="hidden md:block" />);
              } else {
                rowLinks.forEach((link) => {
                  rows.push(
                    <a
                      key={link.url}
                      href={link.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block rounded-lg shadow-sm hover:shadow-md transition-shadow p-6 border border-muted bg-card text-card-foreground group w-full border-l-4"
                      style={{ textDecoration: 'none', borderLeftColor: link.color || 'var(--primary)' }}
                    >
                      <div className="flex items-center gap-3 mb-2">
                        <span className={`text-2xl transition-colors ${link.name === "Github" || link.name === "Skyworks"? "text-black dark:text-white": ""}`}style={link.name !== "Github" && link.name !== "Skyworks"? { color: link.color }: {}}>{link.icon}</span>
                        <span className="font-semibold text-lg text-foreground group-hover:text-primary transition-colors">{link.name}</span>
                      </div>
                      <div className="flex justify-center mt-4">
                        <button
                          className="px-4 py-2 rounded-md bg-muted text-foreground font-medium border border-border hover:bg-accent/20 hover:text-primary transition-colors shadow-none"
                          type="button"
                          tabIndex={-1}
                          onClick={e => { e.preventDefault(); window.open(link.url, '_blank', 'noopener,noreferrer'); }}
                        >
                          {link.button}
                        </button>
                      </div>
                    </a>
                  );
                });
              }
            }
            return rows;
          })()}
        </div>
      </div>
    </section>
  );
}
