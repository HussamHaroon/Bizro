import type { SVGProps } from "react";

/* ------------------------------------------------------------------
   Icons — filled, single-weight, rounded (design.md §4.3).
   Every icon in this page is paired with a word.
------------------------------------------------------------------ */

type IconProps = SVGProps<SVGSVGElement>;

const MicIcon = (p: IconProps) => (
  <svg viewBox="0 0 24 24" width="26" height="26" fill="currentColor" aria-hidden="true" {...p}>
    <path d="M12 2.2a3.1 3.1 0 0 1 3.1 3.1v5.6a3.1 3.1 0 0 1-6.2 0V5.3A3.1 3.1 0 0 1 12 2.2z" />
    <path d="M5.4 10.9a6.6 6.6 0 0 0 13.2 0h-2.2a4.4 4.4 0 0 1-8.8 0H5.4z" />
    <rect x="10.9" y="17.1" width="2.2" height="3.4" rx="1.1" />
    <path d="M8 20.6h8a1.1 1.1 0 0 1 0 2.2H8a1.1 1.1 0 0 1 0-2.2z" />
  </svg>
);

const CameraIcon = (p: IconProps) => (
  <svg viewBox="0 0 24 24" width="26" height="26" fill="currentColor" aria-hidden="true" {...p}>
    <path
      fillRule="evenodd"
      d="M9.4 3.2 8.2 5.7H4.6A2.6 2.6 0 0 0 2 8.3v8.9a2.6 2.6 0 0 0 2.6 2.6h14.8a2.6 2.6 0 0 0 2.6-2.6V8.3a2.6 2.6 0 0 0-2.6-2.6h-3.6l-1.2-2.5H9.4zM12 9.1a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9zm0 2.2a2.3 2.3 0 1 1 0 4.6 2.3 2.3 0 0 1 0-4.6z"
    />
  </svg>
);

const ReportIcon = (p: IconProps) => (
  <svg viewBox="0 0 24 24" width="26" height="26" fill="currentColor" aria-hidden="true" {...p}>
    <path
      fillRule="evenodd"
      d="M15 2.4H6.2A2.2 2.2 0 0 0 4 4.6v14.8a2.2 2.2 0 0 0 2.2 2.2h11.6a2.2 2.2 0 0 0 2.2-2.2V7.4L15 2.4zm.8 14.4a1.05 1.05 0 0 1-1.05 1.05H8.45a1.05 1.05 0 0 1 0-2.1h6.3a1.05 1.05 0 0 1 1.05 1.05zm0-3.7a1.05 1.05 0 0 1-1.05 1.05H8.45a1.05 1.05 0 0 1 0-2.1h6.3a1.05 1.05 0 0 1 1.05 1.05zm-5.55-3.6a1.05 1.05 0 0 1 1.05-1.05h2.4a1.05 1.05 0 0 1 0 2.1h-2.4a1.05 1.05 0 0 1-1.05-1.05z"
    />
  </svg>
);

const RadarIcon = (p: IconProps) => (
  <svg viewBox="0 0 24 24" width="26" height="26" fill="currentColor" aria-hidden="true" {...p}>
    <path
      fillRule="evenodd"
      d="M12 21.4A9.4 9.4 0 1 0 12 2.6v2.3a7.1 7.1 0 1 1-7.1 7.1H2.6A9.4 9.4 0 0 0 12 21.4z"
    />
    <path d="M12 12 20.7 7a9.9 9.9 0 0 0-8.7-5.1V12z" />
    <circle cx="12" cy="12" r="2.3" />
  </svg>
);

const TrailIcon = (p: IconProps) => (
  <svg viewBox="0 0 24 24" width="26" height="26" fill="currentColor" aria-hidden="true" {...p}>
    <rect x="2" y="10.9" width="20" height="2.2" rx="1.1" />
    <circle cx="5" cy="12" r="2.7" />
    <circle cx="12" cy="12" r="2.7" />
    <circle cx="19" cy="12" r="2.7" />
  </svg>
);

const BankIcon = (p: IconProps) => (
  <svg viewBox="0 0 24 24" width="26" height="26" fill="currentColor" aria-hidden="true" {...p}>
    <path d="M12 1.8 1.8 8v2.2h20.4V8L12 1.8z" />
    <rect x="3.6" y="11.9" width="2.7" height="6.6" />
    <rect x="10.65" y="11.9" width="2.7" height="6.6" />
    <rect x="17.7" y="11.9" width="2.7" height="6.6" />
    <rect x="1.8" y="19.9" width="20.4" height="2.4" />
  </svg>
);

const VoicePillIcon = (p: IconProps) => (
  <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true" {...p}>
    <rect x="1.5" y="7" width="21" height="10" rx="5" />
    <path d="M10 9.4v5.2l4.6-2.6L10 9.4z" fill="var(--green)" />
  </svg>
);

const ArrowIcon = (p: IconProps) => (
  <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true" {...p}>
    <path d="M13.3 4.4 21 12l-7.7 7.6-1.7-1.7 4.9-4.9H3.2v-2h13.3l-4.9-4.9 1.7-1.7z" />
  </svg>
);

const PencilIcon = (p: IconProps) => (
  <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true" {...p}>
    <path d="M16.9 2.9 21.1 7.1 8.7 19.5 3 21l1.5-5.7L16.9 2.9zM14.6 8.4l-9 9 .9 2.6 2.6.9 9-9-3.5-3.5z" />
  </svg>
);

/* ------------------------------------------------------------------
   Page
------------------------------------------------------------------ */

export default function App() {
  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>

      <header className="site-header">
        <div className="wrap site-header__inner">
          <a className="wordmark wordmark--img" href="#top" aria-label="Bizro — back to top">
            <img
              src="/brand/wordmark-96.png"
              alt=""
              width={214}
              height={48}
              className="wordmark__logo"
            />
          </a>
          <nav className="site-nav" aria-label="Sections">
            <a href="#problem">Problem</a>
            <a href="#how">How it works</a>
            <a href="#why">Why Bizro</a>
            <a href="#trust">Trust &amp; audit</a>
          </nav>
          <a className="btn btn--primary header-cta" href="/ledger">
            Open dashboard
          </a>
        </div>
      </header>

      <main id="main">
        {/* ---------------- HERO ---------------- */}
        <section className="hero wrap" id="top" aria-labelledby="hero-heading">
          <div className="hero__grid">
            <div>
              <p style={{ margin: 0 }}>
                <span className="sticker">
                  Alkhidmat × Alibaba Cloud AI Hackathon 2026
                </span>
              </p>
              <h1 id="hero-heading">
                The paper khata, given a <span className="hl">memory</span>.
              </h1>
              <p className="lede">
                Bizro is a zero-typing Voice &amp; Vision copilot. It turns the
                WhatsApp voice notes and receipt photos a Pakistani
                micro-entrepreneur already sends into a lender-legible credit
                history — no typing, no new app, no new habit.
              </p>
              <div className="cta-row">
                <a className="btn btn--primary" href="/ledger">
                  Open the live dashboard
                </a>
                <a className="btn btn--ghost" href="#how">
                  See how it works
                </a>
              </div>
            </div>

            {/* Placeholder frame — links to the live app, never fakes a screenshot */}
            <div className="demo-frame">
              <span className="demo-frame__tag">Live demo · placeholder</span>
              <div className="flow-note">
                <span className="flow-note__pill">
                  <VoicePillIcon /> 0:14
                </span>
                <span className="flow-note__text">
                  “Ahmad ko panch hazar ka udhar diya” — the voice note he was
                  sending anyway.
                </span>
              </div>
              <p className="flow-arrow" aria-hidden="true">
                ↓ &nbsp;parsed, not typed
              </p>
              <div className="flow-invoice">
                <div className="flow-invoice__head">
                  <span className="flow-invoice__brand">BIZRO · INVOICE</span>
                  <span className="chip chip--red">UDHAR · ادھار</span>
                </div>
                <div className="flow-invoice__row">
                  <span>Ahmad — credit given</span>
                  <span className="flow-invoice__amount">PKR 5,000</span>
                </div>
                <span className="stamp">AI-Parsed · Confirmed</span>
              </div>
              <a className="demo-frame__link" href="/ledger">
                Open the live ledger <ArrowIcon />
              </a>
            </div>
          </div>
        </section>

        {/* ---------------- PROBLEM ---------------- */}
        <section className="section" id="problem" aria-labelledby="problem-heading">
          <div className="wrap">
            <div className="section-head">
              <span className="chip chip--red">01 · The problem</span>
              <h2 id="problem-heading">
                Creditworthy, but invisible to the lender meant for them.
              </h2>
              <p style={{ margin: "1.2rem 0 0" }}>
                <span className="sticker">
                  The gap isn’t creditworthiness — it’s legibility
                </span>
              </p>
            </div>

            <div className="stats">
              <article className="card stat">
                <span className="chip chip--red">Formal account</span>
                <div className="stat__num stat__num--red">10.3%</div>
                <p>
                  of Pakistani adults hold a formal financial-institution
                  account — at the last national baseline.
                </p>
              </article>

              <article className="card stat">
                <span className="chip chip--teal">South Asia, for contrast</span>
                <div className="stat__num stat__num--teal">~33%</div>
                <p>
                  the South Asian average of adults with a formal
                  financial-institution account.
                </p>
              </article>

              <article className="card stat">
                <span className="chip chip--gold">The blocker</span>
                <div className="stat__word">Shariah-compliant demand</div>
                <p>
                  a meaningful share of small businesses avoiding formal finance
                  cite one specific reason: they are waiting for a
                  Shariah-compliant option, not an interest-bearing one.
                </p>
              </article>
            </div>

            <article className="card mawakmat-card">
              <div>
                <span className="chip chip--green">
                  <BankIcon width="16" height="16" /> Mawakhat · Alkhidmat
                  Foundation
                </span>
                <h3>The interest-free rail already exists</h3>
                <p>
                  Alkhidmat’s Mawakhat program is Qarz-e-Hasna (interest-free)
                  microfinance funded through zakat and sadaqat — the credit
                  product these shopkeepers would actually accept. What it can’t
                  see is a business history that lives in a handwritten
                  notebook.
                </p>
              </div>
              <div>
                <dl className="mini-stats">
                  <div className="mini-stat">
                    <dt>~800</dt>
                    <dd>branches across 400+ cities</dd>
                  </div>
                  <div className="mini-stat">
                    <dt>PKR 30–75k</dt>
                    <dd>typical Qarz-e-Hasna loan</dd>
                  </div>
                  <div className="mini-stat">
                    <dt>99.9%</dt>
                    <dd>repayment rate*</dd>
                  </div>
                </dl>
                <p className="fine">*as claimed by Mawakhat</p>
              </div>
            </article>
          </div>
        </section>

        {/* ---------------- HOW IT WORKS ---------------- */}
        <section className="section" id="how" aria-labelledby="how-heading">
          <div className="wrap">
            <div className="section-head">
              <span className="chip chip--green">02 · How it works</span>
              <h2 id="how-heading">
                Three taps’ worth of effort — months’ worth of credit history.
              </h2>
              <p style={{ margin: "1.2rem 0 0" }}>
                <span className="sticker">Zero typing, all of it</span>
              </p>
            </div>

            <div className="steps">
              <article className="card step">
                <div className="step__top">
                  <span className="chip chip--green">Step 1 · Voice</span>
                  <span className="icon-tile icon-tile--green">
                    <MicIcon />
                  </span>
                </div>
                <h3>Send the voice note</h3>
                <p>
                  A casual Urdu voice note, the way he’d talk to an employee.
                  It’s parsed into a structured sale or credit entry, and a
                  stamped invoice comes straight back on WhatsApp.
                </p>
                <div className="step__badges">
                  <span className="chip chip--gold">Qwen3.5-Omni-Plus</span>
                  <span className="chip">WhatsApp in / out</span>
                </div>
              </article>

              <article className="card step">
                <div className="step__top">
                  <span className="chip chip--gold">Step 2 · Vision</span>
                  <span className="icon-tile icon-tile--gold">
                    <CameraIcon />
                  </span>
                </div>
                <h3>Photograph the receipt</h3>
                <p>
                  One photo of the messy, handwritten supplier receipt. The
                  expense is logged — and obvious pricing errors are flagged
                  before they can hide in a hand-tallied notebook.
                </p>
                <div className="step__badges">
                  <span className="chip chip--gold">Qwen-VL-OCR</span>
                  <span className="chip">Price-error flags</span>
                </div>
              </article>

              <article className="card step">
                <div className="step__top">
                  <span className="chip chip--teal">Step 3 · Report</span>
                  <span className="icon-tile icon-tile--teal">
                    <ReportIcon />
                  </span>
                </div>
                <h3>Tap, months later</h3>
                <p>
                  One tap turns months of accumulated, source-linked history
                  into a Mawakhat-style Credit Readiness Report — with a full
                  audit trail a loan officer can drill into.
                </p>
                <div className="step__badges">
                  <span className="chip chip--gold">Qwen3.7-Plus</span>
                  <span className="chip">Mawakhat-style format</span>
                </div>
              </article>
            </div>
          </div>
        </section>

        {/* ---------------- DIFFERENTIATORS ---------------- */}
        <section className="section" id="why" aria-labelledby="why-heading">
          <div className="wrap">
            <div className="section-head">
              <span className="chip chip--red">03 · Why Bizro</span>
              <h2 id="why-heading">More than “OCR plus a chatbot.”</h2>
              <p style={{ margin: "1.2rem 0 0" }}>
                <span className="sticker">
                  Built for how karyana shops actually run
                </span>
              </p>
            </div>

            <div className="diff-grid">
              <article className="card diff">
                <span className="icon-tile icon-tile--red">
                  <RadarIcon />
                </span>
                <h3>Udhar Radar</h3>
                <p>
                  Flips the expense-tracker lens: Bizro tracks the money
                  customers owe <strong>to the shopkeeper</strong> — the
                  dominant real use of a paper khata, and the piece most
                  digitization tools miss entirely.
                </p>
                <span className="chip chip--red diff__tag">
                  Money owed TO the shop
                </span>
              </article>

              <article className="card diff">
                <span className="icon-tile icon-tile--green">
                  <TrailIcon />
                </span>
                <h3>Audit trail on every entry</h3>
                <p>
                  Every AI-parsed line keeps its source voice note or photo plus
                  a confidence score — and a one-tap correct. A visible trail,
                  not a black box, because a loan officer has to trust the
                  report as much as the shopkeeper trusts the tool.
                </p>
                <span className="chip chip--green diff__tag">
                  Source + confidence, always
                </span>
              </article>

              <article className="card diff">
                <span className="icon-tile icon-tile--gold">
                  <BankIcon />
                </span>
                <h3>A direct line to Mawakhat</h3>
                <p>
                  Not a generic “credit score.” The report is shaped for a
                  lending program that already exists, already has ~800
                  branches, and already has an institutional reason to want
                  exactly this evidence.
                </p>
                <span className="chip chip--gold diff__tag">
                  A real credit rail, not a score
                </span>
              </article>
            </div>
          </div>
        </section>

        {/* ---------------- TRUST / AUDIT ---------------- */}
        <section className="section band" id="trust" aria-labelledby="trust-heading">
          <div className="wrap">
            <div className="band-grid">
              <div className="section-head" style={{ marginBottom: 0 }}>
                <span className="chip chip--gold">04 · Trust &amp; audit</span>
                <h2 id="trust-heading">
                  Every number traces to a voice note or a photo.
                </h2>
                <div className="rule" aria-hidden="true" />
                <p className="lede">
                  The audit trail is the product. In the live app, every field
                  drills down to the original voice note or receipt photo behind
                  it.
                </p>
              </div>

              <div>
                {/* Mock preview of the dashboard's stamp language */}
                <div className="card ledger-mock" aria-label="Mock preview of one audited ledger entry">
                  <div className="ledger-mock__head">
                    <span className="ledger-mock__title">
                      <MicIcon width="18" height="18" /> Ledger entry · 12 Aug
                    </span>
                    <span className="chip chip--red">UDHAR · ادھار</span>
                  </div>

                  <div className="ledger-mock__row">
                    <div>
                      <div className="ledger-mock__name">Ahmad — credit given</div>
                      <span className="urdu" lang="ur" dir="rtl" style={{ fontSize: "0.95rem" }}>
                        پانچ ہزار
                      </span>
                    </div>
                    <span className="ledger-mock__amount">
                      PKR 5,000
                    </span>
                  </div>

                  <ul className="ledger-mock__meta">
                    <li>
                      <MicIcon width="18" height="18" />
                      Source: WhatsApp voice note · 0:14
                    </li>
                    <li>
                      <TrailIcon width="18" height="18" />
                      Parsed by Qwen3.5-Omni-Plus · confidence 96%
                    </li>
                  </ul>

                  <span className="ledger-mock__correct">
                    <PencilIcon /> One-tap correct — the fix is itself a trust
                    signal
                  </span>
                  <span className="stamp ledger-mock__stamp">
                    AI-Parsed · Confirmed
                  </span>
                </div>
                <p className="mock-caption">
                  Mock preview. In the live app each field links to its
                  original audio or photo.
                </p>

                <div className="band-ctas">
                  <a className="btn btn--ghost" href="/ledger">
                    Open the live ledger
                  </a>
                  <a className="btn btn--ghost" href="/credit">
                    See the Credit Readiness Report
                  </a>
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* ---------------- FOOTER ---------------- */}
      <footer className="site-footer">
        <div className="wrap">
          <div className="footer-grid">
            <div>
              <img
                src="/brand/wordmark-96.png"
                alt="Bizro"
                width={214}
                height={48}
                className="wordmark__logo"
              />
              <p className="footer-tagline">The paper khata, given a memory.</p>
            </div>

            <p className="footer-credits">
              Bizro · Bano Qabil × Alibaba Cloud AI Hackathon Pakistan 2026 ·
              built on Alibaba Cloud Model Studio.
              <br />
              Voice Khata by Qwen3.5-Omni-Plus · Vision Audit by Qwen-VL-OCR ·
              Credit Readiness by Qwen3.7-Plus.
            </p>

            <nav className="footer-links" aria-label="Live demo">
              <a href="/ledger">
                Live ledger <ArrowIcon />
              </a>
              <a href="/credit">
                Credit Readiness Report <ArrowIcon />
              </a>
            </nav>
          </div>

          <p className="honesty">
            <strong>Demo build</strong> — AI outputs are clearly labeled when
            running without live keys. Verified figures are sourced in
            design.md §1; the 99.9% Mawakhat repayment rate is as claimed by
            Mawakhat.
          </p>
        </div>
      </footer>
    </>
  );
}
