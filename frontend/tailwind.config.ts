import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        app: {
          base: "#070b14",
          surface: "#0c1322",
          card: "rgba(16, 24, 42, 0.72)",
          cardHover: "rgba(24, 36, 62, 0.85)",
          border: "rgba(255, 255, 255, 0.08)",
          borderGlow: "rgba(99, 102, 241, 0.4)",
        },
        brand: {
          50: "#eef2ff",
          100: "#e0e7ff",
          400: "#818cf8",
          500: "#6366f1",
          600: "#4f46e5",
          700: "#4338ca",
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "monospace"],
      },
      boxShadow: {
        glow: "0 0 25px -5px rgba(99, 102, 241, 0.4)",
        card: "0 20px 40px -15px rgba(0, 0, 0, 0.7)",
        emerald: "0 0 20px -3px rgba(16, 185, 129, 0.35)",
        amber: "0 0 20px -3px rgba(245, 158, 11, 0.35)",
        rose: "0 0 20px -3px rgba(239, 68, 68, 0.35)",
      },
      animation: {
        scan: "scanBeam 3s ease-in-out infinite",
        pulseFast: "pulse 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite",
      },
      keyframes: {
        scanBeam: {
          "0%": { top: "0%", opacity: "0" },
          "15%": { opacity: "1" },
          "85%": { opacity: "1" },
          "100%": { top: "100%", opacity: "0" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
