import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/new_game":            "http://localhost:8000",
      "/action":              "http://localhost:8000",
      "/session":             "http://localhost:8000",
      "/randomize_character": "http://localhost:8000",
    },
  },
});
