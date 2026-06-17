/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        parchment: "#f5f0e8",
        ink: "#1a1a2e",
        ember: "#c0392b",
        gold: "#d4ac0d",
        mist: "#7f8c8d",
      },
      fontFamily: {
        serif: ["Georgia", "Cambria", "serif"],
        mono: ["Fira Code", "monospace"],
      },
    },
  },
  plugins: [],
};
