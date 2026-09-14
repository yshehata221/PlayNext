/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // low-contrast dark surfaces; covers bring the colour, amber is the only accent
        ink: "#0B141C",
        panel: "#111F29",
        field: "#14242F",
        line: "#1E2F3A",
        fog: "#8FA3AE",
        snow: "#E8EEF1",
        amber: "#F2B441",
        coral: "#F26D6D",
        mint: "#5FD3A5",
      },
      fontFamily: {
        sans: ['"Bricolage Grotesque"', "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
