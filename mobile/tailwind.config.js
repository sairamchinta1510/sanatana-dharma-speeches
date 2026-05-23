/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{js,jsx,ts,tsx}", "./components/**/*.{js,jsx,ts,tsx}"],
  presets: [require("nativewind/preset")],
  theme: {
    extend: {
      colors: {
        navy: { DEFAULT: "#0d1117", light: "#161b22", dark: "#090d13" },
        gold: { DEFAULT: "#e2a84b", light: "#f0c56a", dark: "#c48a2e" },
        border: "#21262d",
      },
    },
  },
};
