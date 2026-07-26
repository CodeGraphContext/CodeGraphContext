import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function getOrCreateSessionId(): string {
  if (typeof window === "undefined") return "global";
  let sessionId = localStorage.getItem("cgc-session-id");
  if (!sessionId) {
    sessionId = Math.random().toString(36).substring(2, 8);
    localStorage.setItem("cgc-session-id", sessionId);
  }
  return sessionId;
}
