import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // CargoIQ Design System (from DESIGN_SPEC.md)
        canvas:  "#F1F4F8",
        surface: "#FFFFFF",
        subtle:  "#E8ECF1",
        inset:   "#D8DDE5",
        nav: {
          DEFAULT: "#1A2332",
          active:  "#243447",
          hover:   "#1F2D3D",
          text:    "#C8D3DF",
          muted:   "#6B7E92",
          border:  "#243040",
        },
        accent: {
          DEFAULT: "#B8860B",
          hover:   "#9A700A",
          subtle:  "#FDF3DC",
          border:  "#D4A843",
        },
        text: {
          primary:   "#0D1B2A",
          secondary: "#3D5166",
          tertiary:  "#6B7E92",
          disabled:  "#9AAAB8",
          inverse:   "#F1F4F8",
        },
        border: {
          DEFAULT: "#C8D0DA",
          strong:  "#9AAAB8",
          subtle:  "#DDE3EA",
        },
        success: {
          DEFAULT: "#15632A",
          bg:      "#EBF5EE",
          border:  "#8EC9A0",
        },
        warning: {
          DEFAULT: "#7A4F00",
          bg:      "#FEF6E7",
          border:  "#E8B84B",
        },
        error: {
          DEFAULT: "#9B1C1C",
          bg:      "#FEF2F2",
          border:  "#F5A5A5",
        },
        info: {
          DEFAULT: "#1A4971",
          bg:      "#EBF3FB",
          border:  "#93C5E4",
        },
      },
      fontFamily: {
        sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "sans-serif"],
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
      fontSize: {
        "2xs": ["11px", { lineHeight: "1.4" }],
        xs:    ["13px", { lineHeight: "1.5" }],
        sm:    ["14px", { lineHeight: "1.6" }],
        base:  ["15px", { lineHeight: "1.5" }],
        lg:    ["17px", { lineHeight: "1.5" }],
        xl:    ["20px", { lineHeight: "1.3" }],
        "2xl": ["24px", { lineHeight: "1.2" }],
        "3xl": ["30px", { lineHeight: "1.15" }],
      },
      borderRadius: {
        sm:  "3px",
        DEFAULT: "4px",
        md:  "4px",
        lg:  "6px",
        xl:  "8px",
      },
      boxShadow: {
        sm:  "0 1px 2px rgba(13,27,42,0.06)",
        DEFAULT: "0 2px 8px rgba(13,27,42,0.08)",
        lg:  "0 4px 20px rgba(13,27,42,0.12)",
        xl:  "0 8px 32px rgba(13,27,42,0.16)",
      },
    },
  },
  plugins: [],
};
export default config;
