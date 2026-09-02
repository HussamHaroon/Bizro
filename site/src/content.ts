/* Homepage copy in the three Bizro languages (same triad as the dashboard:
   ur | en | mixed). The law from the owner (2026-08-30): no duplicated
   sentences — a visitor reads ONE language per mode.
     en    — plain English.
     mixed — the house voice: English copy with Urdu accents where they are
             brand, not translation (بزرو, ادھار chips, stickers). This is the
             default and the hackathon-showcase mode.
     ur    — full Urdu, rendered RTL in Nastaliq (html[dir=rtl] via the
             provider). Latin tech names (Qwen…, PKR, 10.3%) stay Latin —
             that is how Urdu tech writing actually works. */

import { MITHU_GUIDE_COPY } from "./mithu-content";

export type Lang = "ur" | "en" | "mixed";

export const LANGS: { id: Lang; label: string; title: string }[] = [
  { id: "ur", label: "اردو", title: "Urdu" },
  { id: "mixed", label: "Mixed", title: "Mixed — English with Urdu accents" },
  { id: "en", label: "English", title: "English" },
];

const en = {
  a11y: {
    skip: "Skip to content",
    nav: "Sections",
    langLabel: "Language",
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
      "Bizro is a zero-typing Voice & Vision copilot. It turns the WhatsApp voice notes and receipt photos a Pakistani micro-entrepreneur already sends into a lender-legible credit history — no typing, no new app, no new habit.",
    ctaPrimary: "Open the live dashboard",
    ctaSecondary: "See how it works",
    demoTag: "Live demo · placeholder",
    voiceLine:
      "“I gave Ahmad five thousand on credit” — the voice note he was sending anyway.",
    flowArrow: "↓  parsed, not typed",
    invoiceBrand: "BIZRO · INVOICE",
    udharChip: "CREDIT",
    invoiceName: "Ahmad — credit given",
    invoiceAmount: "PKR 5,000",
    stamp: "AI-Parsed · Confirmed",
    link: "Open the live ledger",
  },
  movie: {
    label: "Bizro in four scenes — an animated title sequence",
    sr:
      "Animated sequence: scattered pieces of a paper ledger — a voice note, a receipt, a notebook — fly together and assemble into a golden Bizro coin that stamps down like a trust seal, revealing Bizro's three tools: Voice Khata, Vision Audit, and the Credit Readiness Report.",
    captions: [
      "He sends the voice note. He snaps the receipt. That's the whole job.",
      "No typing. The pieces assemble themselves into a ledger entry.",
      "Every entry is stamped — parsed, priced, and double-checked.",
      "Months of this become a credit history a lender can actually read.",
    ],
  },
  problem: {
    chip: "01 · The problem",
    h2: "Creditworthy, but invisible to the lender meant for them.",
    sticker: "The gap isn’t creditworthiness — it’s legibility",
    stats: [
      {
        chip: "Formal account",
        tone: "red",
        num: "10.3%",
        text:
          "of Pakistani adults hold a formal financial-institution account — at the last national baseline.",
      },
      {
        chip: "South Asia, for contrast",
        tone: "teal",
        num: "~33%",
        text: "the South Asian average of adults with a formal financial-institution account.",
      },
      {
        chip: "The blocker",
        tone: "gold",
        num: "Shariah-compliant demand",
        isWord: true,
        text:
          "a meaningful share of small businesses avoiding formal finance cite one specific reason: they are waiting for a Shariah-compliant option, not an interest-bearing one.",
      },
    ],
    mawakhat: {
      chip: "Mawakhat · Alkhidmat Foundation",
      h3: "The interest-free rail already exists",
      p:
        "Alkhidmat’s Mawakhat program is Qarz-e-Hasna (interest-free) microfinance funded through zakat and sadaqat — the credit product these shopkeepers would actually accept. What it can’t see is a business history that lives in a handwritten notebook.",
      minis: [
        { dt: "~800", dd: "branches across 400+ cities" },
        { dt: "PKR 30–75k", dd: "typical Qarz-e-Hasna loan" },
        { dt: "99.9%", dd: "repayment rate*" },
      ],
      fine: "*as claimed by Mawakhat",
    },
  },
  how: {
    chip: "02 · How it works",
    h2: "Three taps’ worth of effort — months’ worth of credit history.",
    sticker: "Zero typing, all of it",
    steps: [
      {
        chip: "Step 1 · Voice",
        h3: "Send the voice note",
        p:
          "A casual Urdu voice note, the way he’d talk to an employee. It’s parsed into a structured sale or credit entry, and a stamped invoice comes straight back on WhatsApp.",
        badges: ["Qwen3.5-Omni-Plus", "WhatsApp in / out"],
      },
      {
        chip: "Step 2 · Vision",
        h3: "Photograph the receipt",
        p:
          "One photo of the messy, handwritten supplier receipt. The expense is logged — and obvious pricing errors are flagged before they can hide in a hand-tallied notebook.",
        badges: ["Qwen-VL-OCR", "Price-error flags"],
      },
      {
        chip: "Step 3 · Report",
        h3: "Tap, months later",
        p:
          "One tap turns months of accumulated, source-linked history into a Mawakhat-style Credit Readiness Report — with a full audit trail a loan officer can drill into.",
        badges: ["Qwen3.7-Plus", "Mawakhat-style format"],
      },
    ],
  },
  why: {
    chip: "03 · Why Bizro",
    h2: "More than “OCR plus a chatbot.”",
    sticker: "Built for how corner stores actually run",
    cards: [
      {
        h3: "Credit Radar",
        pPre: "Flips the expense-tracker lens: Bizro tracks the money customers owe ",
        pStrong: "to the shopkeeper",
        pPost:
          " — the dominant real use of a paper ledger, and the piece most digitization tools miss entirely.",
        tag: "Money owed TO the shop",
      },
      {
        h3: "Audit trail on every entry",
        pPre: "",
        pStrong: "",
        pPost:
          "Every AI-parsed line keeps its source voice note or photo plus a confidence score — and a one-tap correct. A visible trail, not a black box, because a loan officer has to trust the report as much as the shopkeeper trusts the tool.",
        tag: "Source + confidence, always",
      },
      {
        h3: "A direct line to Mawakhat",
        pPre: "",
        pStrong: "",
        pPost:
          "Not a generic “credit score.” The report is shaped for a lending program that already exists, already has ~800 branches, and already has an institutional reason to want exactly this evidence.",
        tag: "A real credit rail, not a score",
      },
    ],
  },
  trust: {
    chip: "04 · Trust & audit",
    h2: "Every number traces to a voice note or a photo.",
    lede:
      "The audit trail is the product. In the live app, every field drills down to the original voice note or receipt photo behind it.",
    mock: {
      title: "Ledger entry · 12 Aug",
      udharChip: "CREDIT",
      name: "Ahmad — credit given",
      urduAmount: "Five thousand",
      amount: "PKR 5,000",
      source: "Source: WhatsApp voice note · 0:14",
      parsed: "Parsed by Qwen3.5-Omni-Plus · confidence 96%",
      correct: "One-tap correct — the fix is itself a trust signal",
      stamp: "AI-Parsed · Confirmed",
      caption:
        "Mock preview. In the live app each field links to its original audio or photo.",
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
      "Demo build — AI outputs are clearly labeled when running without live keys. Verified figures are sourced in design.md §1; the 99.9% Mawakhat repayment rate is as claimed by Mawakhat.",
  },
  mithu: {
    heroLabel: "Mithu the parrot presents the live demo preview",
    ...MITHU_GUIDE_COPY.en,
  },
};

export type Copy = typeof en;

/* ---- Mixed = the current house voice (English + Urdu brand accents). ---- */
const mixed: Copy = {
  ...en,
  a11y: { ...en.a11y, langLabel: "زبان · Language" },
  hero: {
    ...en.hero,
    h1Pre: "The paper khata, given a ",
    voiceLine:
      "“Ahmad ko panch hazar ka udhar diya” — the voice note he was sending anyway.",
    udharChip: "UDHAR · ادھار",
    ctaSecondary: "دیکھیں · See how it works",
    stamp: "AI-Parsed · Confirmed",
    link: "Open the live ledger · کھولیں",
  },
  problem: {
    ...en.problem,
    sticker: "The gap isn’t creditworthiness — it’s legibility · پہچان کی کمی",
    mawakhat: {
      ...en.problem.mawakhat,
      h3: "The interest-free rail already exists · بلا سود",
    },
  },
  how: { ...en.how, sticker: "Zero typing, all of it · ٹائپنگ صفر" },
  why: {
    ...en.why,
    sticker: "Built for how karyana shops actually run · کریانہ",
    cards: [
      {
        ...en.why.cards[0],
        h3: "Udhar Radar",
        pPost:
          " — the dominant real use of a paper khata, and the piece most digitization tools miss entirely.",
      },
      ...en.why.cards.slice(1),
    ],
  },
  trust: {
    ...en.trust,
    mock: {
      ...en.trust.mock,
      udharChip: "UDHAR · ادھار",
      urduAmount: "پانچ ہزار",
      stamp: "AI-Parsed · Confirmed · تصدیق شدہ",
    },
  },
  footer: { ...en.footer, tagline: "The paper khata, given a memory · کھاتہ" },
  mithu: {
    ...en.mithu,
    heroLabel: "Mithu · مٹھو presents the live demo preview",
    ...MITHU_GUIDE_COPY.mixed,
  },
};

/* ---- Full Urdu (RTL). Latin tech names stay Latin by design. ---- */
const ur: Copy = {
  a11y: { skip: "مواد پر جائیں", nav: "حصے", langLabel: "زبان" },
  nav: {
    problem: "مسئلہ",
    how: "کیسے چلتا ہے",
    why: "بزرو کیوں",
    trust: "اعتماد اور آڈٹ",
    cta: "ڈیش بورڈ کھولیں",
  },
  hero: {
    sticker: "الخدمت × علی بابا کلاؤڈ اے آئی ہیکاتھون پاکستان 2026",
    h1Pre: "کاغذی کھاتے کو مل ایک ",
    h1Hl: "یادداشت",
    h1Post: "۔",
    lede:
      "بزرو ایک زیرو-ٹائپنگ وائس اینڈ وژن کوپائلٹ ہے۔ یہ پاکستانی چھوٹے کاروباری کے وہی وٹس ایپ وائس نوٹس اور رسیدوں کی تصاویر — جنہیں وہ پہلے ہی بھیجتا ہے — قرض دہندے کے قابلِ مطالعہ کریڈٹ ہسٹری میں بدل دیتا ہے۔ نہ کوئی ٹائپنگ، نہ نیا ایپ، نہ کوئی نئی عادت۔",
    ctaPrimary: "لائیو ڈیش بورڈ کھولیں",
    ctaSecondary: "کیسے کام کرتا ہے دیکھیں",
    demoTag: "لائیو ڈیمو · نمائش",
    voiceLine:
      "»احمد کو پانچ ہزار کا ادھار دیا« — وہی وائس نوٹ جو وہ پہلے ہی بھیج رہا تھا۔",
    flowArrow: "↓  پارس ہوا، ٹائپ نہیں کیا گیا",
    invoiceBrand: "بزرو · بلان",
    udharChip: "ادھار",
    invoiceName: "احمد — قرض دیا",
    invoiceAmount: "PKR 5,000",
    stamp: "اے آئی پارس · تصدیق شدہ",
    link: "لائیو کھاتہ کھولیں",
  },
  movie: {
    label: "بزرو چار مناظر میں — ایک متحرک عنوانی فلم",
    sr:
      "متحرک سلسلہ: کاغذی کھاتے کے بکھرے ٹکڑے — ایک وائس نوٹ، ایک رسید، ایک کاپی — اڑ کر جُڑتے ہیں اور سنہرے بزرو سکے کی شکل لے لیتے ہیں جو اعتماد کی مہر کی طرح نشست لگاتا ہے، اور بزرو کے تین اوزار آشکار ہوتے ہیں: وائس کھاتہ، وژن آڈٹ، اور کریڈٹ ریڈینیس رپورٹ۔",
    captions: [
      "وہ وائس نوٹ بھیجتا ہے، رسید کی تصویر لیتا ہے۔ بس یہی اس کا کام ہے۔",
      "ٹائپنگ صفر۔ ٹکڑے خود جُڑ کر کھاتے کا اندراج بن جاتے ہیں۔",
      "ہر اندراج پر مہر ہوتی ہے — پارس، قیمت جانچ، دوبارہ تصدیق۔",
      "مہینوں کا یہ ریکارڈ ایسی کریڈٹ ہسٹری بن جاتا ہے جو قرض دہندہ واقعی پڑھ سکتا ہے۔",
    ],
  },
  problem: {
    chip: "01 · مسئلہ",
    h2: "قرض کے اہل، مگر اُس قرض دہندے کے لیے غیر مرئی جو اُن کے لیے بنا ہے۔",
    sticker: "کمی اہلیت کی نہیں — پہچان کی ہے",
    stats: [
      {
        chip: "سرکاری اکاؤنٹ",
        tone: "red",
        num: "10.3%",
        text:
          "پاکستانی بالغوں کا اتنا حصہ کسی سرکاری مالیاتی ادارے میں اکاؤنٹ رکھتا ہے — آخری قومی سروے کے مطابق۔",
      },
      {
        chip: "جنوبی ایشیا، مقابلے کے لیے",
        tone: "teal",
        num: "~33%",
        text: "جنوبی ایشیا میں سرکاری مالیاتی اکاؤنٹ رکھنے والے بالغوں کی اوسط۔",
      },
      {
        chip: "اصل رکاوٹ",
        tone: "gold",
        num: "شریعہ سے ہم آہنگ آپشن",
        isWord: true,
        text:
          "سرکاری فنانس سے گریز کرنے والے چھوٹے کاروباروں کا بڑا حصہ ایک وجہ بتاتا ہے: وہ سود خور آپشن نہیں، شریعہ سے ہم آہنگ آپشن کے منتظر ہیں۔",
      },
    ],
    mawakhat: {
      chip: "مواکھات · الخدمت فاؤنڈیشن",
      h3: "بلا سود کریڈٹ کی سہولت پہلے سے موجود ہے",
      p:
        "الخدمت کا پروگرامِ مواکھات زکوٰۃ اور صدقات سے چلنے والا قرضِ حسنہ (بلا سود) مائیکرو فنانس ہے — وہی کریڈٹ جو یہ دکاندار واقعی قبول کریں گے۔ مگر اسے وہ کاروباری تاریخ نظر نہیں آتی جو ایک ہاتھ سے لکھے کھاتے میں قید ہے۔",
      minis: [
        { dt: "~800", dd: "400+ شہروں میں برانچز" },
        { dt: "PKR 30–75k", dd: "عام قرضِ حسنہ" },
        { dt: "99.9%", dd: "واپسی کی شرح*" },
      ],
      fine: "*جیسا کہ مواکھات کا دعویٰ ہے",
    },
  },
  how: {
    chip: "02 · کیسے چلتا ہے",
    h2: "تین ٹیپ کی محنت — مہینوں کی کریڈٹ ہسٹری۔",
    sticker: "ٹائپنگ صفر، با سب کچھ",
    steps: [
      {
        chip: "قدم 1 · آواز",
        h3: "وائس نوٹ بھیجیں",
        p:
          "ایک عام اردو وائس نوٹ، جیسے وہ کسی ملازم سے بات کرتا۔ بزرو اسے فروخت یا ادھار کے ساختہ اندراج میں پارس کرتا ہے، اور وٹس ایپ پر مہر شدہ بل فوراً واپس آتا ہے۔",
        badges: ["Qwen3.5-Omni-Plus", "وٹس ایپ in / out"],
      },
      {
        chip: "قدم 2 · بصیرت",
        h3: "رسید کی تصویر بنائیں",
        p:
          "گندے، ہاتھ سے لکھے سپلائر رسید کی صرف ایک تصویر۔ خرچ درج ہو جاتا ہے — اور ظاہر قیمت کی غلطیاں کھاتے میں چھپنے سے پہلے نشان زد ہو جاتی ہیں۔",
        badges: ["Qwen-VL-OCR", "قیمت-غلطی کے نشان"],
      },
      {
        chip: "قدم 3 · رپورٹ",
        h3: "ٹیپ کریں، مہینوں بعد",
        p:
          "ایک ٹیپ مہینوں کی جمع شدہ، ماخذ سے جُڑی تاریخ کو مواکھات طرز کی کریڈٹ ریڈینیس رپورٹ میں بدل دیتا ہے — مکمل آڈٹ ٹریل کے ساتھ جس میں لون آفیسر تفصیل تک اتر سکتا ہے۔",
        badges: ["Qwen3.7-Plus", "مواکھات طرز کا فارمیٹ"],
      },
    ],
  },
  why: {
    chip: "03 · بزرو کیوں",
    h2: "صرف ”اے آئی پڑھائے، بوٹ جواب دے“ سے زیادہ۔",
    sticker: "کریانہ دکانوں کے اصل چلن کے لیے بنایا گیا",
    cards: [
      {
        h3: "ادھار ریڈار",
        pPre: "خرچ ٹریکر کا الٹ رخ: بزرو اُن رقموں کو ٹریک کرتا ہے جو گاہکوں نے ",
        pStrong: "دکاندار کو",
        pPost:
          " دینے ہیں — کاغذی کھاتے کا سب سے بڑا حقیقی استعمال، جو ڈیجیٹلائزیشن ٹولز اکثر بالکل بھول جاتے ہیں۔",
        tag: "دکان کو ملنے والی رقم",
      },
      {
        h3: "ہر اندراج پر آڈٹ ٹریل",
        pPre: "",
        pStrong: "",
        pPost:
          "ہر اے آئی پارس شدہ سطر اپنا ماخذ — وائس نوٹ یا تصویر — اور اعتماد کا اسکور ساتھ رکھتی ہے، اور ایک ٹیپ میں درست بھی ہو جاتی ہے۔ ظاہر نشان، سیاہ خانہ نہیں؛ کیونکہ لون آفیسر کو رپورٹ پر اتنا ہی بھروسا چاہیے جتنا دکاندار کو ٹول پر۔",
        tag: "ماخذ + اعتماد، ہمیشہ",
      },
      {
        h3: "مواکھات سے سیدھا رابطہ",
        pPre: "",
        pStrong: "",
        pPost:
          "کوئی عمومی ”کریڈٹ سکور“ نہیں۔ رپورٹ ایک ایسے قرضی پروگرام کے لیے ڈھالی گئی ہے جو پہلے سے موجود ہے، پہلے ہی ~800 برانچز رکھتا ہے، اور اسی ثبوت کی ادارتی ضرورت بھی رکھتا ہے۔",
        tag: "اصل کریڈٹ ریل، محض سکور نہیں",
      },
    ],
  },
  trust: {
    chip: "04 · اعتماد اور آڈٹ",
    h2: "ہر عدد کسی وائس نوٹ یا تصویر تک پہنچتا ہے۔",
    lede:
      "آڈٹ ٹریل ہی پروڈکٹ ہے۔ لائیو ایپ میں ہر فیلڈ اپنے اصل وائس نوٹ یا رسید کی تصویر تک کھولتی ہے۔",
    mock: {
      title: "کھاتہ اندراج · 12 اگست",
      udharChip: "ادھار",
      name: "احمد — قرض دیا",
      urduAmount: "پانچ ہزار",
      amount: "PKR 5,000",
      source: "ماخذ: وٹس ایپ وائس نوٹ · 0:14",
      parsed: "پارس: Qwen3.5-Omni-Plus · اعتماد 96%",
      correct: "ایک ٹیپ میں درستگی — درستگی خود بھروسے کا اشارہ ہے",
      stamp: "اے آئی پارس · تصدیق شدہ",
      caption: "نمونہ پیش نظارہ۔ لائیو ایپ میں ہر فیلڈ اصل آڈیو یا تصویر سے جُڑی ہوتی ہے۔",
    },
    ctaLedger: "لائیو کھاتہ کھولیں",
    ctaReport: "کریڈٹ ریڈینیس رپورٹ دیکھیں",
  },
  footer: {
    tagline: "کاغذی کھاتہ، اب یادداشت کے ساتھ۔",
    credits1:
      "بزرو · بانو قبیل × علی بابا کلاؤڈ اے آئی ہیکاتھون پاکستان 2026 · علی بابا کلاؤڈ ماڈل اسٹوڈیو پر تعمیر۔",
    credits2:
      "وائس کھاتہ: Qwen3.5-Omni-Plus · وژن آڈٹ: Qwen-VL-OCR · کریڈٹ ریڈینیس: Qwen3.7-Plus۔",
    linkLedger: "لائیو کھاتہ",
    linkReport: "کریڈٹ ریڈینیس رپورٹ",
    honesty:
      "ڈیمو بلڈ — لائیو کیز کے بغیر چلتے ہوئے اے آئی آؤٹ پٹ واضح طور پر لیبل ہوتے ہیں۔ تصدیق شدہ اعداد design.md §1 میں ماخذ ہیں؛ مواکھات کی 99.9% واپسی کی شرح مواکھات کے دعوے کے مطابق ہے۔",
  },
  mithu: {
    heroLabel: "مٹھو طوطا لائیو ڈیمو کی پیش کش کرتا ہوا",
    ...MITHU_GUIDE_COPY.ur,
  },
};

export const CONTENT: Record<Lang, Copy> = { en, mixed, ur };
