import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        canvas: "#0b1120",
        card: "#111a2e",
        "card-hover": "#16223b",
        navy: {
          950: "#070d18",
          900: "#0a1120",
          850: "#0c1322",
          800: "#0e1627",
          700: "#131f38",
          600: "#1e293b",
          500: "#334155",
        },
        brand: {
          600: "#2563eb",
          500: "#3b82f6",
          400: "#60a5fa",
        },
      },
      borderColor: {
        subtle: "rgba(255, 255, 255, 0.08)",
        highlight: "rgba(255, 255, 255, 0.16)",
      },
    },
  },
  plugins: [],
};
export default config;

