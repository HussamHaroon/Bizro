/* Homepage copy — ONE language, plain English (owner directive 2026-09-04:
   "make it in english, remove the other modes for urdu and mixed, keep
   everything in english, and use simple wordings so anyone can understand").

   Law for every string: short sentences, everyday words. The old triad
   (ur | en | mixed) is gone — there is no language state anywhere in the
   site; components read this single COPY object.

   Brand facts stay exact even though the wording got simpler: 10.3% /
   ~33% formal-account shares, the Shariah-compliant demand blocker,
   Mawakhat (Alkhidmat Foundation) with ~800 branches, PKR 30–75k
   Qarz-e-Hasna loans, the 99.9% repayment rate (as claimed), the Qwen
   model names, and the PKR 5,000 / Ahmad / 96% demo figures. */

import { MITHU_COPY } from "./mithu-content";

export const COPY = {
  a11y: {
    skip: "Skip to content",
    nav: "Sections",
  },
  nav: {
    problem: "Problem",
    how: "How it works",
    why: "Why Bizro",
    trust: "Trust & audit",
    cta: "Open dashboard",
  },
  hero: {
    sticker: "Alkhidmat × Alibaba Cloud AI Hackathon 2026",
    h1Pre: "The paper ledger, given a ",
    h1Hl: "memory",
    h1Post: ".",
    lede:
      "Bizro turns the WhatsApp voice notes and receipt photos a shopkeeper already sends into a written ledger and a credit history a lender can read. No typing. No new app.",
    ctaPrimary: "Open the live dashboard",
    ctaSecondary: "See how it works",
    demoTag: "Live demo · try it",
    voiceLine:
      "“I gave Ahmad five thousand on credit” — the voice note he was already sending.",
    flowArrow: "↓  read by AI, not typed",
    invoiceBrand: "BIZRO · INVOICE",
    creditChip: "CREDIT",
    invoiceName: "Ahmad — credit given",
    invoiceAmount: "PKR 5,000",
    stamp: "AI-Parsed · Confirmed",
    link: "Open the live ledger",
    micIdle: "Tap to record a note",
    micListening: "Listening…",
    micDenied: "No microphone access. Allow it in your browser, or use the chat link below.",
    micUnavailable: "This browser can't record — open the full WhatsApp chat instead",
    reading: "Bizro is reading your note…",
    confirming: "Confirming…",
    kindWords: {
      sale: "sale",
      expense: "expense",
      udhar_given: "credit given",
      udhar_settlement: "payment received",
    } as Record<string, string>,
    stampPending: "AI-Parsed · Pending",
    confirmBtn: "It's correct",
    changeBtn: "Change",
    sendAnother: "Send another",
    busyError: "The free AI service is busy. Please try again in a minute.",
    mockNote: "Mock mode — AI answers are simulated (no live key)",
    parseMiss: "Bizro couldn't read an entry from that note. Its reply:",
    freeTierNote: "Each recording uses 1–2 free AI requests.",
    chatLink: "Open the full WhatsApp chat",
  },
  movie: {
    label: "Bizro in four scenes — an animated title sequence",
    sr:
      "Animated sequence: scattered pieces of a paper ledger — a voice note, a receipt, a notebook — fly together and assemble into a golden Bizro coin that stamps down like a trust seal, revealing Bizro's three tools: Voice Khata, Vision Audit, and the Credit Readiness Report.",
    captions: [
      "He sends the voice note. He snaps the receipt. That's the whole job.",
      "No typing. The pieces join up into one ledger entry.",
      "Every entry gets a stamp — read, priced, and double-checked.",
      "Months of this add up to a credit history a lender can read.",
    ],
  },
  problem: {
    chip: "01 · The problem",
    h2: "Their businesses are real. A lender just can't see them.",
    sticker: "Real businesses. Invisible records.",
    stats: [
      {
        chip: "Bank account",
        tone: "red",
        num: "10.3%",
        text: "of adults in Pakistan have an account at a bank or formal financial institution.",
      },
      {
        chip: "South Asia, for comparison",
        tone: "teal",
        num: "~33%",
        text: "the average share of adults with a formal account across South Asia.",
      },
      {
        chip: "The blocker",
        tone: "gold",
        num: "Shariah-compliant demand",
        isWord: true,
        text:
          "many small shops that avoid formal loans give the same reason: they are waiting for a Shariah-compliant option, not an interest-based one.",
      },
    ],
    mawakhat: {
      chip: "Mawakhat · Alkhidmat Foundation",
      h3: "The interest-free option already exists",
      p:
        "Alkhidmat's Mawakhat program gives Qarz-e-Hasna loans — interest-free money paid for by zakat and sadaqat. It is the kind of credit these shopkeepers will actually accept. What Mawakhat can't see is the business history trapped in a handwritten notebook.",
      minis: [
        { dt: "~800", dd: "branches across 400+ cities" },
        { dt: "PKR 30–75k", dd: "a typical Qarz-e-Hasna loan" },
        { dt: "99.9%", dd: "repayment rate*" },
      ],
      fine: "*as claimed by Mawakhat",
    },
  },
  how: {
    chip: "02 · How it works",
    h2: "Three taps of effort. Months of credit history.",
    sticker: "No typing anywhere",
    steps: [
      {
        chip: "Step 1 · Voice",
        h3: "Send a voice note",
        p:
          "He records a short voice note on WhatsApp — the way he'd tell a helper. Bizro turns it into a ledger entry and sends a stamped invoice right back.",
        badges: ["Qwen3.5-Omni-Plus", "WhatsApp in / out"],
      },
      {
        chip: "Step 2 · Vision",
        h3: "Photograph the receipt",
        p:
          "One photo of the handwritten supplier receipt. The expense is logged, and obvious price mistakes get flagged before they hide in the notebook.",
        badges: ["Qwen-VL-OCR", "Price-error flags"],
      },
      {
        chip: "Step 3 · Report",
        h3: "One tap, months later",
        p:
          "One tap turns months of saved notes and photos into a Mawakhat-style Credit Readiness Report. Every number links back to its source, so a loan officer can check it.",
        badges: ["Qwen3.7-Plus", "Mawakhat-style format"],
      },
    ],
  },
  why: {
    chip: "03 · Why Bizro",
    h2: "More than “a scanner plus a chatbot.”",
    sticker: "Built for how corner shops really run",
    cards: [
      {
        h3: "Credit Radar",
        pPre: "Other tools count what you spend. Bizro tracks the money customers owe ",
        pStrong: "the shopkeeper",
        pPost:
          " — the most common line in a paper ledger, and the one most tools miss.",
        tag: "Money owed TO the shop",
      },
      {
        h3: "A trail behind every entry",
        pPre: "",
        pStrong: "",
        pPost:
          "Every AI-parsed line keeps its original voice note or photo, a confidence score, and a one-tap fix. An open trail, not a black box — a loan officer can check every number.",
        tag: "Source + confidence, always",
      },
      {
        h3: "A direct line to Mawakhat",
        pPre: "",
        pStrong: "",
        pPost:
          "This is not a generic “credit score.” The report is shaped for a lender that already exists, already has ~800 branches, and already wants exactly this proof.",
        tag: "A real credit rail, not a score",
      },
    ],
  },
  trust: {
    chip: "04 · Trust & audit",
    h2: "Every number traces back to a voice note or a photo.",
    lede:
      "The audit trail is the product. In the live app, every field opens the original voice note or receipt photo behind it.",
    mock: {
      title: "Ledger entry · 12 Aug",
      creditChip: "CREDIT",
      name: "Ahmad — credit given",
      amount: "PKR 5,000",
      source: "Source: WhatsApp voice note · 0:14",
      parsed: "Parsed by Qwen3.5-Omni-Plus · confidence 96%",
      correct: "One tap to fix — the fix itself builds trust",
      stamp: "AI-Parsed · Confirmed",
      caption:
        "Mock preview. In the live app, each field links to its original audio or photo.",
    },
    ctaLedger: "Open the live ledger",
    ctaReport: "See the Credit Readiness Report",
  },
  footer: {
    tagline: "The paper ledger, given a memory.",
    credits1:
      "Bizro · Bano Qabil × Alibaba Cloud AI Hackathon Pakistan 2026 · built on Alibaba Cloud Model Studio.",
    credits2:
      "Voice Khata by Qwen3.5-Omni-Plus · Vision Audit by Qwen-VL-OCR · Credit Readiness by Qwen3.7-Plus.",
    linkLedger: "Live ledger",
    linkReport: "Credit Readiness Report",
    honesty:
      "Demo build — AI answers are clearly labeled when no live key is connected. Verified figures are sourced in design.md §1; the 99.9% Mawakhat repayment rate is as claimed by Mawakhat.",
  },
  mithu: {
    heroLabel: "Mithu the parrot presents the live demo",
    ...MITHU_COPY,
  },
};

export type Copy = typeof COPY;
