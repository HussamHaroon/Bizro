import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

/* The two most-used webfonts (body 400 + bold 700, latin subset) are discovered
   by the browser only after CSS parse. Preload them with the HTML instead.
   Vite hashes emitted asset names, so the tags cannot be hardcoded in
   index.html — they are injected from the bundle at build time. */
function preloadFonts(names: string[]): Plugin {
  return {
    name: "preload-fonts",
    apply: "build",
    enforce: "post",
    generateBundle(_options, bundle) {
      const html = bundle["index.html"];
      if (!html || html.type !== "asset") return;
      const tags = names
        .map((n) =>
          Object.keys(bundle).find((k) => k.endsWith(".woff2") && k.includes(n)),
        )
        .filter((f): f is string => f !== undefined)
        .map(
          (f) =>
            `<link rel="preload" href="/${f}" as="font" type="font/woff2" crossorigin />`,
        )
        .join("\n    ");
      if (tags) {
        html.source = String(html.source).replace("</head>", `${tags}\n  </head>`);
      }
    },
  };
}

// Static single-page marketing site. No router, no aliases — keep it buildable offline.
// Served from the origin root; /ledger and /credit are the live dashboard routes.
//
// In production ONE origin (the backend, :8000) serves this site at / and the
// dashboard at /ledger, /credit, /settings — so the cross-app links are
// same-origin and just work. The dev server is a second origin with no
// dashboard: Vite's SPA fallback answers /ledger with THIS site's index.html,
// the router-less app re-renders the homepage, and "Open the live dashboard"
// looks dead. Proxy the dashboard's routes, its built assets and the API back
// to the backend so dev matches production. Dev-only; needs the backend up;
// the build is unaffected. /assets and /api are unused by this site in dev
// (its modules come from /src), so the prefixes are free to forward.
const BACKEND = "http://localhost:8000";

export default defineConfig({
  plugins: [
    react(),
    preloadFonts([
      "ibm-plex-sans-latin-400-normal",
      "ibm-plex-sans-latin-700-normal",
    ]),
  ],
  build: {
    target: "es2020",
  },
  server: {
    proxy: {
      "/ledger": BACKEND,
      "/credit": BACKEND,
      "/settings": BACKEND,
      "/assets": BACKEND,
      "/api": BACKEND,
    },
  },
});
