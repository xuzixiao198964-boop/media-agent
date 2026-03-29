/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
    passWithNoTests: false,
  },
  server: {    port: 5173,
    proxy: {
      "/api": { target: "http://127.0.0.1:9090", changeOrigin: true },
      "/uploads": { target: "http://127.0.0.1:9090", changeOrigin: true },
      "/media": { target: "http://127.0.0.1:9090", changeOrigin: true },
      "/health": { target: "http://127.0.0.1:9090", changeOrigin: true },
    },
  },
});
