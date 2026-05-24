/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // Mines navy sidebar
        navy: {
          900: "#0f1a36",
          800: "#152141",
          700: "#1c2a52",
          600: "#243466",
          500: "#3a4a82",
          400: "#5d6ea3",
          300: "#8b97bd",
          200: "#c1cae0",
          100: "#dde3f0",
          50:  "#eef1f8",
        },
        // Gold / copper accent
        gold: {
          700: "#9a7a2f",
          600: "#b48a3a",
          500: "#c89e54",
          400: "#d4b272",
          300: "#e3c993",
          200: "#f0dcb4",
          100: "#fbf3df",
        },
        // Greys (light theme)
        ink: {
          900: "#0f172a",
          800: "#1f2937",
          700: "#334155",
          600: "#475569",
          500: "#64748b",
          400: "#94a3b8",
          300: "#cbd5e1",
          200: "#e2e8f0",
          100: "#f1f5f9",
          50: "#f8fafc",
        },
        // Semantic
        ok:     { 50: "#ecfdf5", 200: "#a7f3d0", 600: "#059669", 700: "#047857" },
        warn:   { 50: "#fffbeb", 200: "#fde68a", 600: "#d97706", 700: "#b45309" },
        danger: { 50: "#fef2f2", 100: "#fee2e2", 200: "#fecaca", 600: "#dc2626", 700: "#b91c1c" },
        info:   { 50: "#eff6ff", 200: "#bfdbfe", 600: "#2563eb", 700: "#1d4ed8" },
        // Soft RAG citation pill
        cite:   { 50: "#f5f3ff", 200: "#ddd6fe", 600: "#7c3aed", 700: "#6d28d9" },
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
        display: [
          "Sora",
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "sans-serif",
        ],
        mono: [
          "JetBrains Mono",
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "monospace",
        ],
      },
      letterSpacing: {
        tightish: "-0.011em",
      },
      boxShadow: {
        card: "0 1px 2px rgba(15,23,42,0.04), 0 1px 3px rgba(15,23,42,0.04)",
        pop: "0 4px 10px rgba(15,23,42,0.06), 0 2px 4px rgba(15,23,42,0.04)",
        lg: "0 10px 24px rgba(15,23,42,0.08), 0 4px 10px rgba(15,23,42,0.04)",
      },
      borderRadius: {
        xl: "0.75rem",
        "2xl": "1rem",
      },
    },
  },
  plugins: [],
};
