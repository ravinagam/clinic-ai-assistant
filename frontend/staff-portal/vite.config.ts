import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  envDir: "../../",
  plugins: [react()],
  server: {
    port: 3003,
    proxy: {
      "/staff": "http://localhost:8080",
    },
  },
});
