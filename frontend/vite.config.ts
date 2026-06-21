import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // dev 専用: フロント(5173) の /api/* を backend(8000) へ中継（CORS 不要）。本番配信は別途。
  server: {
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
