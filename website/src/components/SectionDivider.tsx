import React from "react";
import { cn } from "@/lib/utils";

interface SectionDividerProps {
  className?: string;
  variant?: "wave" | "mesh" | "dots" | "line";
}

const SectionDivider = ({ className, variant = "line" }: SectionDividerProps) => {
  if (variant === "line") {
    return (
      <div className={cn("w-full flex items-center justify-center py-4", className)}>
        <div className="w-full max-w-4xl h-[1px] bg-gradient-to-r from-transparent via-border to-transparent" />
      </div>
    );
  }

  // Fallback to simple line for all variants to maintain minimalism
  return (
    <div className={cn("absolute inset-0 pointer-events-none flex items-center justify-center opacity-30", className)}>
      <div className="w-full h-[1px] bg-border" />
    </div>
  );
};

export default SectionDivider;
