import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  envDir: "../../",
  plugins: [react()],
  server: {
    port: 3004,
    proxy: {
      "/doctor": "http://localhost:8080",
      "/staff": "http://localhost:8080",
    },
  },
});
