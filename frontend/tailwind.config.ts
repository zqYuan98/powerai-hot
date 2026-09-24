import type { Config } from "tailwindcss";

// 与原型一致的设计令牌（深色科技风）。组件内大量使用精确渐变/阴影，
// 故保留内联 style 以保证像素级还原；此处令牌供工具类与扩展使用。
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0A0C12",
        panel: "#0C111C",
        panel2: "#090C14",
         textmain: "#E6EBF4",
        blue: "#3B9EFF",
        cyan: "#34E0D8",
        violet: "#A78BFA",
        amber: "#FBBF24",
        rose: "#FB7185",
        emerald: "#34D399",
      },
      fontFamily: {
        sans: ["'Noto Sans SC'", "sans-serif"],
        display: ["'Space Grotesk'", "sans-serif"],
        mono: ["'JetBrains Mono'", "monospace"],
      },
    },
  },
  plugins: [],
};
export default config;
