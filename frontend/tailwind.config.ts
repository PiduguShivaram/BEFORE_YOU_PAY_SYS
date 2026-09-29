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
          card: "rgba(13, 21, 39, 0.95)",
          cardHover: "rgba(18, 30, 54, 0.98)",
          cardSubtle: "rgba(16, 26, 48, 0.8)",
          cardInset: "rgba(9, 14, 28, 0.9)",
          border: "rgba(255, 255, 255, 0.08)",
          borderSubtle: "rgba(255, 255, 255, 0.04)",
          borderStrong: "rgba(255, 255, 255, 0.16)",
          borderGlow: "rgba(99, 102, 241, 0.3)",
        },
        brand: {
          50: "#eef2ff",
          100: "#e0e7ff",
          200: "#c7d2fe",
          300: "#a5b4fc",
          400: "#818cf8",
          500: "#6366f1",
          600: "#4f46e5",
          700: "#4338ca",
          800: "#3730a3",
          900: "#312e81",
        },
        status: {
          pass: "#10b981",
          passBg: "rgba(16, 185, 129, 0.08)",
          passBorder: "rgba(16, 185, 129, 0.25)",
          verification: "#f59e0b",
          verificationBg: "rgba(245, 158, 11, 0.08)",
          verificationBorder: "rgba(245, 158, 11, 0.25)",
          inconclusive: "#60a5fa",
          inconclusiveBg: "rgba(96, 165, 250, 0.08)",
          inconclusiveBorder: "rgba(96, 165, 250, 0.25)",
          info: "#94a3b8",
          infoBg: "rgba(148, 163, 184, 0.08)",
          infoBorder: "rgba(148, 163, 184, 0.2)",
          error: "#f43f5e",
          errorBg: "rgba(244, 63, 94, 0.08)",
          errorBorder: "rgba(244, 63, 94, 0.25)",
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "monospace"],
      },
      boxShadow: {
        card: "0 10px 30px -10px rgba(0, 0, 0, 0.5)",
        elevated: "0 20px 40px -15px rgba(0, 0, 0, 0.7)",
        subtle: "0 1px 3px 0 rgba(0, 0, 0, 0.3)",
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
