import React from "react";
import { FaGlobe, FaYoutube, FaMedium, FaTwitter, FaReddit, FaGithub, FaBook, FaBullhorn, FaStackOverflow, FaRegNewspaper } from "react-icons/fa";
import { SiVercel } from "react-icons/si";
import GlassCard from "./GlassCard";
import SectionDivider from "./SectionDivider";

export default function SocialMentionsTimeline() {
  const links = [
    { name: "Website", url: "https://codegraphcontext.vercel.app/", icon: <FaGlobe />, color: "hsl(263 70% 65%)", button: "Check our website" },
    { name: "Youtube", url: "https://www.youtube.com/watch?v=KYYSdxhg1xU", icon: <FaYoutube />, color: "#FF0000", button: "Watch on YouTube" },
    { name: "Blog", url: "https://medium.com/@shashankshekharsingh1205/building-codegraphcontext-my-end-term-journey-in-summer-of-bitcoin-2025-422c9a4dc87e", icon: <FaMedium />, color: "#02B875", button: "Read the blog" },
    { name: "Twitter", url: "https://x.com/braidpool/status/1968683721625637203", icon: <FaTwitter />, color: "#1DA1F2", button: "View on Twitter/X" },
    { name: "PulseMCP", url: "https://www.pulsemcp.com/servers/codegraphcontext", icon: <FaBullhorn />, color: "#6366F1", button: "See on PulseMCP" },
    { name: "MCPMarket", url: "https://mcpmarket.com/server/codegraphcontext", icon: <FaBook />, color: "#6366F1", button: "View on MCPMarket" },
    { name: "Playbooks", url: "https://playbooks.com/mcp/codegraphcontext", icon: <FaBook />, color: "#6366F1", button: "Open Playbook" },
    { name: "MCPHunt", url: "https://mcp-hunt.com/mcp/server/codegraphcontext", icon: <FaRegNewspaper />, color: "#6366F1", button: "See on MCPHunt" },
    { name: "StackerNews", url: "https://stacker.news/items/1227191", icon: <FaStackOverflow />, color: "#F48024", button: "See on StackerNews" },
    { name: "Glama.ai", url: "https://glama.ai/mcp/servers/@CodeGraphContext/CodeGraphContext/blob/a346d340d8f705ce93626b4b322dd0e2823ba46b/src/codegraphcontext/core/jobs.py", icon: <FaGlobe />, color: "hsl(180 100% 70%)", button: "See on Glama.ai" },
    { name: "Github", url: "https://github.com/punkpeye/awesome-mcp-servers?tab=readme-ov-file#coding-agents", icon: <FaGithub />, color: "#ffffff", button: "See on GitHub" },
    { name: "Mcpservers.org", url: "https://mcpservers.org/servers/CodeGraphContext/codegraphcontext", icon: <FaGlobe />, color: "hsl(263 70% 65%)", button: "See on Mcpservers.org" },
    { name: "Skyworks", url: "https://skywork.ai/skypage/en/codegraph-smart-code-companion/1978349276941164544", icon: <SiVercel />, color: "#ffffff", button: "See on Skyworks" },
    { name: "Reddit", url: "https://www.reddit.com/r/mcp/comments/1o22gc5/i_built_codegraphcontext_an_mcp_server_that/", icon: <FaReddit />, color: "#FF5700", button: "See Reddit post" },
  ];

  return (
    <section className="py-24 px-4 relative bg-black">
      <SectionDivider variant="wave" className="absolute top-0 left-0 right-0 z-0 opacity-40" />
      <div className="container mx-auto max-w-7xl relative z-10">
        <div className="text-center mb-16">
          <h2 className="text-3xl sm:text-4xl md:text-5xl font-black mb-6 text-white uppercase tracking-tight py-2">
            Social Mentions & Recognitions
          </h2>
          <p className="text-[10px] font-mono text-gray-500 uppercase tracking-widest max-w-3xl mx-auto">
            CodeGraphContext has been recognized and mentioned across top platforms. Here are some highlights from our journey:
          </p>
        </div>
        
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {links.map((link) => (
            <a
              key={link.url}
              href={link.url}
              target="_blank"
              rel="noopener noreferrer"
              className="block group"
            >
              <GlassCard 
                className="h-full p-6 transition-all duration-300 relative overflow-hidden filter grayscale hover:grayscale-0" 
                hoverable={true}
              >
                {/* Colored accent line on the left */}
                <div 
                  className="absolute left-0 top-0 bottom-0 w-1 opacity-0 group-hover:opacity-100 transition-opacity"
                  style={{ backgroundColor: link.color }}
                />
                
                <div className="flex flex-col h-full pl-3">
                  <div className="flex items-center gap-4 mb-4">
                    <div 
                      className="p-3 rounded-full bg-purple-600 text-white group-hover:scale-110 transition-transform duration-300"
                    >
                      <span className="text-xl">{link.icon}</span>
                    </div>
                    <span className="font-black text-sm uppercase tracking-widest text-white transition-colors">
                      {link.name}
                    </span>
                  </div>
                  
                  <div className="mt-auto pt-4 flex items-center justify-between">
                    <span className="text-[10px] font-mono uppercase tracking-widest text-gray-500 group-hover:text-white transition-colors">
                      {link.button}
                    </span>
                    <span className="text-white opacity-0 group-hover:opacity-100 transition-opacity transform translate-x-[-10px] group-hover:translate-x-0 duration-300 font-bold">
                      →
                    </span>
                  </div>
                </div>
              </GlassCard>
            </a>
          ))}
        </div>
      </div>
    </section>
  );
}
