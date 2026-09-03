import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

/* Test-only config. Kept separate from vite.config.ts so the production build
   is untouched. `globals: false` — every test imports { describe, it, expect }
   from "vitest" explicitly, which means tsconfig.json needs no `types` entry
   and the product TS config stays exactly as shipped. */
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    // A valid origin so jsdom provides a working in-memory localStorage; the
    // default opaque origin makes window.localStorage throw on access.
    environmentOptions: { jsdom: { url: "http://localhost/" } },
    globals: false,
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    restoreMocks: true,
  },
});
