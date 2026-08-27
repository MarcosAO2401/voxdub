/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        bg: "#0E0F13",
        surface: "#171922",
        border: "#262A36",
        accent: "#5B8DEF",
        accent2: "#3DDC97",
        text: "#E6E8EC",
        muted: "#8A90A2",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      borderRadius: { DEFAULT: "10px", lg: "12px" },
    },
  },
  plugins: [],
};
