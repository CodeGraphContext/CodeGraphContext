import React from "react";
import { cn } from "@/lib/utils";

interface GlassCardProps {
  children: React.ReactNode;
  className?: string;
  glowColor?: "purple" | "cyan" | "green" | "none"; // Kept for prop compatibility, but no actual glow used
  hoverable?: boolean;
}

const GlassCard = ({
  children,
  className,
  glowColor = "none",
  hoverable = true,
}: GlassCardProps) => {
  return (
    <div
      className={cn(
        "bg-black border border-white/10 rounded-3xl transition-all duration-300",
        hoverable ? "hover:border-purple-500/40 hover:bg-purple-500/5" : "",
        className
      )}
    >
      {children}
    </div>
  );
};

export default GlassCard;
