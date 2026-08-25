import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

/* Fonts ship as npm packages (design-tokens/README.md) — the demo never depends on
   reaching Google Fonts. Weights actually used by the token styles:
   body IBM Plex Sans 400/500/600/700 · Urdu UI Noto Sans (aliased) 400/600 ·
   numerals Zilla Slab 400/600/700 · display Nastaliq 400. */
import '@fontsource/ibm-plex-sans/400.css';
import '@fontsource/ibm-plex-sans/500.css';
import '@fontsource/ibm-plex-sans/600.css';
import '@fontsource/ibm-plex-sans/700.css';
import '@fontsource/noto-sans-arabic/400.css';
import '@fontsource/noto-sans-arabic/600.css';
import '@fontsource/zilla-slab/400.css';
import '@fontsource/zilla-slab/600.css';
import '@fontsource/zilla-slab/700.css';
import '@fontsource/noto-nastaliq-urdu/400.css';

import './index.css';
import { App } from './App';
import { LanguageProvider } from './i18n';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <LanguageProvider>
      <App />
    </LanguageProvider>
  </StrictMode>,
);
