/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // Warm & Approachable direction (teal/amber), per
        // .claude/skills/dashboard-design/SKILL.md - exact values from the
        // design skill, not approximations of Tailwind's default palette.
        brand: {
          DEFAULT: "#0F6E56",
          light: "#E1F5EE",
          dark: "#04342C",
          darker: "#085041",
        },
        amber: {
          bg: "#FAEEDA",
          text: "#633806",
          strong: "#854F0B",
        },
      },
      borderRadius: {
        lg: "10px",
        xl: "12px",
      },
      fontFamily: {
        sans: ["'Plus Jakarta Sans'", "Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["'JetBrains Mono'", "ui-monospace", "SFMono-Regular", "monospace"],
      },
    },
  },
  plugins: [],
};
