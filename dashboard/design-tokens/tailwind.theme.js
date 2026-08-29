/* Bizro Tailwind theme — 1:1 mapping of design-tokens/tokens.css (design.md §4
   + D4-1 "stamped-ledger" neobrutalist extension). Values must never drift from
   tokens.css. If Tailwind v4 (CSS-first config) is used instead, import the
   @theme block equivalent of these exact values — the CSS file remains the
   source of truth. D3-4 gradients/soft shadows are retired with D4-1. */

module.exports = {
  theme: {
    extend: {
      colors: {
        ink: {
          green: '#0B5D3B',
          greenHover: '#0E7A4C',
          greenDisabled: '#7FA392',
          line: '#1F1B16',
        },
        paper: {
          DEFAULT: '#F5F1E6',
          raised: '#FCF9F0',
          cream: '#F7F2E7',      /* EXTERNAL anchor (invoice/report renderers) */
          creamRaised: '#FDFAF2',/* EXTERNAL anchor (invoice/report renderers) */
        },
        ledger: { red: '#A6332B', redHover: '#C04A41' },
        seal: { gold: '#C98A2C' },
        settled: { teal: '#1F7A6C', tealInk: '#176156' },
        rule: { line: '#DCD3BE' }, /* EXTERNAL anchor (invoice/report renderers) */
        /* D4-1 punchy semantic fills — text on fills: paper on green/red/teal,
           ink-line on gold (AA, see tokens.css pair list). */
        fill: {
          green: '#0B5D3B',
          red: '#A6332B',
          gold: '#E9A93D',
          teal: '#1F7A6C',
        },
        gridline: 'rgba(31, 27, 22, 0.20)',
      },
      fontFamily: {
        body: ['"IBM Plex Sans"', '"Noto Sans Urdu"', 'system-ui', 'sans-serif'],
        numerals: ['"Zilla Slab"', '"IBM Plex Sans"', 'serif'],
        displayUr: ['"Noto Nastaliq Urdu"', 'serif'],
      },
      fontSize: {
        /* D3-4 type-scale bump kept (older-user skew, design.md §4.7):
           body copy 15px, meta 13px. */
        xs: '13px',
        sm: '15px',
      },
      borderRadius: {
        card: '2px',
        button: '2px',
        chip: '0px',
      },
      spacing: {
        touch: '48px',
      },
      transitionDuration: {
        fast: '200ms',
        stamp: '300ms',
      },
      /* D4-1 hard offset shadows — zero blur, ink-line color. */
      boxShadow: {
        'hard-sm': '3px 3px 0 #1F1B16',
        'hard-md': '5px 5px 0 #1F1B16',
        'hard-lg': '8px 8px 0 #1F1B16',
        none: 'none',
      },
    },
  },
};
