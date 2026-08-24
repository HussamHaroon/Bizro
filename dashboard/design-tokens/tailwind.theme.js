/* Bizro "Khata Modern" Tailwind theme — 1:1 mapping of design-tokens/tokens.css
   (design.md §4.1–4.2). Values must never drift from tokens.css. If Tailwind v4
   (CSS-first config) is used instead, import the @theme block equivalent of these
   exact values — the CSS file remains the source of truth. */

module.exports = {
  theme: {
    extend: {
      colors: {
        ink: {
          green: '#0B5D3B',
          greenHover: '#0E7A4C',
          greenDisabled: '#7FA392',
          black: '#211E1A',
        },
        paper: {
          cream: '#F7F2E7',
          raised: '#FDFAF2',
        },
        ledger: { red: '#A6332B', redHover: '#C04A41' },
        seal: { gold: '#C98A2C' },
        settled: { teal: '#1F7A6C' },
        rule: { line: '#DCD3BE' },
      },
      fontFamily: {
        body: ['"IBM Plex Sans"', '"Noto Sans Urdu"', 'system-ui', 'sans-serif'],
        numerals: ['"Zilla Slab"', '"IBM Plex Sans"', 'serif'],
        displayUr: ['"Noto Nastaliq Urdu"', 'serif'],
      },
      borderRadius: {
        card: '6px',
        button: '6px',
      },
      spacing: {
        touch: '48px',
      },
      transitionDuration: {
        fast: '200ms',
        stamp: '300ms',
      },
      boxShadow: {
        none: 'none',
      },
    },
  },
};
