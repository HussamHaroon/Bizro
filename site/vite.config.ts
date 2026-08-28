import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Static single-page marketing site. No router, no aliases — keep it buildable offline.
// Served from the origin root; /ledger and /credit are the live dashboard routes.
export default defineConfig({
  plugins: [react()],
  build: {
    target: "es2020",
  },
});
