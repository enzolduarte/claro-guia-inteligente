import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Aproximações da identidade Claro — não são tokens oficiais.
        claro: {
          red: "#E4002B",
          dark: "#B00020",
          ink: "#16181d",
          soft: "#f6f7f9",
        },
      },
    },
  },
  plugins: [],
};
export default config;
