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
          deep: '#073D27',
          black: '#211E1A',
        },
        paper: {
          cream: '#F7F2E7',
          raised: '#FDFAF2',
        },
        canvas: '#FAFAF8',
        ledger: { red: '#A6332B', redHover: '#C04A41' },
        seal: { gold: '#C98A2C', goldBright: '#E3AC55', goldDeep: '#A8731F' },
        settled: { teal: '#1F7A6C', tealBright: '#2F9C8A', tealInk: '#176156' },
        rule: { line: '#DCD3BE' },
      },
      backgroundImage: {
        'bizro-header':
          'linear-gradient(135deg, #0B5D3B 0%, #073D27 100%)',
        'bizro-card':
          'linear-gradient(180deg, #FDFAF2 0%, #F7F2E7 100%)',
        'bizro-bar-in':
          'linear-gradient(180deg, #2F9C8A 0%, #1F7A6C 100%)',
        'bizro-bar-out':
          'linear-gradient(180deg, #C04A41 0%, #A6332B 100%)',
        'bizro-udhar-h':
          'linear-gradient(90deg, #0E7A4C 0%, #073D27 100%)',
      },
      fontFamily: {
        body: ['"IBM Plex Sans"', '"Noto Sans Urdu"', 'system-ui', 'sans-serif'],
        numerals: ['"Zilla Slab"', '"IBM Plex Sans"', 'serif'],
        displayUr: ['"Noto Nastaliq Urdu"', 'serif'],
      },
      fontSize: {
        /* D3-4 type-scale bump (mirrors the @theme overrides in src/index.css):
           body copy 15px, meta 13px — one notch up globally. */
        xs: '13px',
        sm: '15px',
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
