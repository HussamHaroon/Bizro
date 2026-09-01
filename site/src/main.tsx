import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/500.css";
import "@fontsource/ibm-plex-sans/600.css";
import "@fontsource/ibm-plex-sans/700.css";
import "@fontsource/zilla-slab/600.css";
import "@fontsource/zilla-slab/700.css";
import "@fontsource/noto-nastaliq-urdu/400.css";
import "@fontsource/noto-nastaliq-urdu/700.css";

import "./styles.css";
import { SiteLangProvider } from "./site-i18n";
import App from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <SiteLangProvider>
      <App />
    </SiteLangProvider>
  </StrictMode>,
);
