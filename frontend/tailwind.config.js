/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          50: "#f5f0ff",
          100: "#ede5ff",
          500: "#7c3aed",
          600: "#6d28d9",
          900: "#1e0a4a",
        },
        panel: "#1a1a2e",
      },
      fontFamily: {
        comic: ["Bangers", "cursive"],
        body: ["Inter", "sans-serif"],
      },
      animation: {
        "panel-in": "panel-in 0.4s ease-out forwards",
        pulse: "pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
      },
      keyframes: {
        "panel-in": {
          "0%": {opacity: "0", transform: "scale(0.95)"},
          "100%": {opacity: "1", transform: "scale(1)"},
        },
      },
    },
  },
  plugins: [],
};
