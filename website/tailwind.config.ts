import type { Config } from "tailwindcss";

export default {
  darkMode: ["class"],
  content: ["./pages/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./app/**/*.{ts,tsx}", "./src/**/*.{ts,tsx}"],
  prefix: "",
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
          dim: "#5b21b6",
          light: "#9061f9",
        },
        void: "#06060a",
        deep: "#0a0a10",
        surface: "#101018",
        elevated: "#16161f",
        hover: "#1c1c28",
        "border-subtle": "#1e1e2a",
        "border-default": "#2a2a3a",
        "text-primary": "#e4e4ed",
        "text-secondary": "#8888a0",
        "text-muted": "#5a5a70",
        "node-file": "#3b82f6",
        "node-folder": "#6366f1",
        "node-class": "#f59e0b",
        "node-function": "#10b981",
        "node-interface": "#ec4899",
        "node-method": "#14b8a6",
      },
      backgroundImage: {
        "gradient-primary": "var(--gradient-primary)",
        "gradient-hero": "var(--gradient-hero)",
        "gradient-card": "var(--gradient-card)",
      },
      boxShadow: {
        "glow": "var(--shadow-glow)",
        "glow-soft": "0 0 40px rgba(124,58,237,0.15)",
        "glow-yellow": "0 0 20px rgba(234,179,8,0.4)",
        "card": "var(--shadow-card)",
      },
      transitionTimingFunction: {
        "smooth": "var(--transition-smooth)",
        "bounce": "var(--transition-bounce)",
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      keyframes: {
        "accordion-down": {
          from: {
            height: "0",
          },
          to: {
            height: "var(--radix-accordion-content-height)",
          },
        },
        "accordion-up": {
          from: {
            height: "var(--radix-accordion-content-height)",
          },
          to: {
            height: "0",
          },
        },
        breathe: {
          "0%, 100%": { "border-color": "#2a2a3a", "box-shadow": "0 0 0 0 rgba(124,58,237,0.3)" },
          "50%": { "border-color": "#7c3aed", "box-shadow": "0 0 40px 10px rgba(124,58,237,0.3)" },
        },
        "pulse-glow": {
          "0%, 100%": { transform: "scale(1)", "box-shadow": "0 0 40px rgba(124,58,237,0.4)" },
          "50%": { transform: "scale(1.1)", "box-shadow": "0 0 80px rgba(124,58,237,0.6)" },
        },
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        "slide-up": {
          from: { opacity: "0", transform: "translateY(20px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
        breathe: "breathe 3s ease-in-out infinite",
        "pulse-glow": "pulse-glow 2s ease-in-out infinite",
        "fade-in": "fade-in 0.3s ease-out",
        "slide-up": "slide-up 0.3s ease-out",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
} satisfies Config;
