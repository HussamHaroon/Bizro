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
import { attachButtonSfx } from "./sfx";
import App from "./App";

// One delegated button-click sound layer (lazy AudioContext, muted-aware,
// fail-silent). Attaching only adds a listener — no audio work happens
// until a real user click, which is a valid gesture.
attachButtonSfx();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <SiteLangProvider>
      <App />
    </SiteLangProvider>
  </StrictMode>,
);
