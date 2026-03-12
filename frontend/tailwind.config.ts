import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    "./auth.ts",
  ],
  theme: {
    extend: {
      colors: {
        primary: "#0f766e",
        accent: "#f59e0b",
        surface: "#f7f7f2",
        ink: "#1f2937",
      },
      boxShadow: {
        card: "0 14px 40px -28px rgba(15, 118, 110, 0.5)",
      },
    },
  },
  plugins: [],
};

export default config;
