import { resolve } from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Two pages: the product landing page and the white-label briefing board (one app, every airline).
export default defineConfig({
  base: "./",
  plugins: [react()],
  build: {
    rollupOptions: {
      input: { main: resolve(__dirname, "index.html"), board: resolve(__dirname, "board/index.html") },
    },
  },
  server: { port: 5190, strictPort: true },
  preview: { port: 4190, strictPort: true },
});
