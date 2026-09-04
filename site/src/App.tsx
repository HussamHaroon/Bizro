import { useEffect, useRef, useState, type SVGProps } from "react";
import LazyScrollMovie from "./LazyScrollMovie";
import { GuideMithu, Mithu, SfxToggle } from "./Mascot";
import { useReveal } from "./useReveal";
import { COPY, type Copy } from "./content";
import {
  VoiceRecorder,
  blobToBase64,
  buildButtonEnvelope,
  buildVoiceEnvelope,
  formatAmountPkr,
  formatElapsed,
  interpretButtonResponse,
  interpretVoiceResponse,
  postWebhook,
  recorderSupported,
  type HeroResult,
} from "./hero-demo";

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
      d="M9 4.6c.4-.9 1.2-1.4 2.2-1.4h1.6c1 0 1.8.5 2.2 1.4l.5 1h2.7A2.6 2.6 0 0 1 20.8 8.2v9A2.6 2.6 0 0 1 18.2 19.8H5.8a2.6 2.6 0 0 1-2.6-2.6v-9a2.6 2.6 0 0 1 2.6-2.6h2.7l.5-1z"
    />
    <circle cx="12" cy="12.4" r="3.6" fill="var(--green)" />
  </svg>
);

const ReportIcon = (p: IconProps) => (
  <svg viewBox="0 0 24 24" width="26" height="26" fill="currentColor" aria-hidden="true" {...p}>
    <path
      d="M6 2.4h9.2L19.6 6.8V20a1.6 1.6 0 0 1-1.6 1.6H6A1.6 1.6 0 0 1 4.4 20V4A1.6 1.6 0 0 1 6 2.4z"
    />
  </svg>
);

const RadarIcon = (p: IconProps) => (
  <svg viewBox="0 0 24 24" width="26" height="26" fill="currentColor" aria-hidden="true" {...p}>
    <path
      d="M12 2.1a9.9 9.9 0 1 1-9.9 9.9A9.9 9.9 0 0 1 12 2.1zm0 4.4v5.5l4.8 2.8"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.6"
      strokeLinecap="round"
      strokeLinejoin="round"
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

const CheckIcon = (p: IconProps) => (
  <svg
    viewBox="0 0 24 24"
    width="20"
    height="20"
    fill="none"
    stroke="currentColor"
    strokeWidth="3.2"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
    {...p}
  >
    <path d="M4 12.6 9.4 18 20 6.8" />
  </svg>
);

/* ------------------------------------------------------------------
   Hero demo — the REAL pipeline behind the demo-frame (helpers in
   hero-demo.ts). A tap records a voice note (browser MediaRecorder),
   stop POSTs it to /webhook/whatsapp in the exact simulator envelope
   shape, and the invoice updates with what the server ACTUALLY parsed.
   States: example (the static read — kept until a real answer exists)
   → recording → processing → result | rejected | error. Quick replies
   (§7.1) post the button-reply envelope; the stamp flips to confirmed.
   Honesty law: missing fields render as missing — never invented — and
   the server's mock marker is shown as-is.
------------------------------------------------------------------ */

type DemoPhase =
  | "example"
  | "recording"
  | "processing"
  | "result"
  | "confirming"
  | "rejected"
  | "error";

function DemoFrame({ hero }: { hero: Copy["hero"] }) {
  const [micSupported] = useState(recorderSupported);
  const [phase, setPhase] = useState<DemoPhase>("example");
  const [result, setResult] = useState<HeroResult | null>(null);
  const [serverReply, setServerReply] = useState<string | null>(null);
  const [micFailed, setMicFailed] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const recorderRef = useRef<VoiceRecorder | null>(null);
  const startedAtRef = useRef(0);

  const recording = phase === "recording";
  const busy = phase === "processing" || phase === "confirming";

  // elapsed timer (mm:ss) — ticks only while recording
  useEffect(() => {
    if (!recording) return;
    const tick = () =>
      setElapsed(Math.floor((Date.now() - startedAtRef.current) / 1000));
    tick();
    const id = window.setInterval(tick, 500);
    return () => window.clearInterval(id);
  }, [recording]);

  // teardown an in-flight take when the frame goes away
  useEffect(() => () => recorderRef.current?.dispose(), []);

  async function toggleRecording() {
    if (recording) {
      await stopAndSend();
      return;
    }
    if (busy) return;
    const rec = new VoiceRecorder();
    try {
      await rec.start();
    } catch {
      setMicFailed(true);
      setPhase("error");
      return;
    }
    recorderRef.current = rec;
    startedAtRef.current = Date.now();
    setElapsed(0);
    setPhase("recording");
  }

  async function stopAndSend() {
    const rec = recorderRef.current;
    if (!rec) return;
    setPhase("processing");
    try {
      const blob = await rec.stop();
      recorderRef.current = null;
      if (!blob || blob.size === 0) {
        // the take produced nothing — a mic problem, not a busy tier
        setMicFailed(true);
        setPhase("error");
        return;
      }
      const mediaB64 = await blobToBase64(blob);
      const outcome = await interpretVoiceResponse(
        await postWebhook(buildVoiceEnvelope(mediaB64)),
      );
      if (outcome.rejected) {
        // the pipeline really answered: nothing persisted, reply shown as-is
        setServerReply(outcome.reply);
        setResult(null);
        setPhase("rejected");
        return;
      }
      setServerReply(null);
      setResult(outcome.result);
      setPhase("result");
    } catch {
      setPhase("error");
    }
  }

  async function pressQuickReply(id: string) {
    const btn = result?.buttons.find((b) => b.id === id);
    if (!btn || busy) return;
    setPhase("confirming");
    try {
      const out = interpretButtonResponse(
        await postWebhook(buildButtonEnvelope(btn.id, btn.title)),
      );
      if (out.reply) setServerReply(out.reply);
      setResult((prev) =>
        prev ? { ...prev, buttons: [], status: out.status ?? prev.status } : prev,
      );
      setPhase("result");
    } catch {
      setPhase("error");
    }
  }

  function reset() {
    setPhase("example");
    setResult(null);
    setServerReply(null);
    setMicFailed(false);
    setElapsed(0);
  }

  // Invoice line — real parsed data once the server gave it, the static
  // example only BEFORE first use. Missing fields render as "—", never faked.
  const kindWord = result?.kind
    ? hero.kindWords[result.kind] ?? result.kind
    : null;
  let invoiceName: string;
  if (!result) {
    invoiceName = hero.invoiceName;
  } else if (result.counterparty && kindWord) {
    invoiceName = `${result.counterparty} — ${kindWord}`;
  } else {
    invoiceName = result.counterparty ?? kindWord ?? "—";
  }
  const invoiceAmount =
    result && result.amountPkr !== null
      ? formatAmountPkr(result.amountPkr)
      : result
        ? "PKR —"
        : hero.invoiceAmount;
  const isExpense = result?.kind === "expense";
  const chipLabel = !result
    ? hero.creditChip
    : isExpense
      ? kindWord ?? hero.creditChip
      : hero.creditChip;
  const confirmed = result?.status === "confirmed";

  const micRow = (
    <button
      type="button"
      className={`hero-demo__mic${recording ? " is-recording" : ""}`}
      onClick={toggleRecording}
      disabled={busy}
      aria-pressed={recording}
    >
      {recording ? (
        <>
          <span className="hero-demo__dot" aria-hidden="true" />
          <span className="hero-demo__timer">{formatElapsed(elapsed)}</span>
          <span>{hero.micListening}</span>
        </>
      ) : (
        <>
          <MicIcon />
          <span>{hero.micIdle}</span>
        </>
      )}
    </button>
  );

  const noMicRow = (
    <a className="hero-demo__mic hero-demo__mic--link" href="/simulator">
      <MicIcon />
      <span>{hero.micUnavailable}</span>
    </a>
  );

  return (
    <div className="demo-frame">
      <span className="demo-frame__tag">{hero.demoTag}</span>

      {/* mic (or its graceful fallback) + the example line it fulfills */}
      <div className="hero-demo__mic-row">{micSupported ? micRow : noMicRow}</div>
      <p className="hero-demo__caption">
        <VoicePillIcon /> {hero.voiceLine}
      </p>

      <p className="flow-arrow" aria-hidden="true">
        {hero.flowArrow}
      </p>

      {busy && (
        <p className="hero-demo__status" role="status">
          {phase === "confirming" ? hero.confirming : hero.reading}
        </p>
      )}

      {phase === "error" && (
        <p className="hero-demo__alert" role="alert">
          {micFailed ? hero.micDenied : hero.busyError}
        </p>
      )}

      {phase === "rejected" && (
        <div className="hero-demo__miss" role="status">
          <p className="hero-demo__miss-label">{hero.parseMiss}</p>
          {serverReply && (
            <p className="hero-demo__reply urdu" lang="ur" dir="rtl">
              {serverReply}
            </p>
          )}
        </div>
      )}

      <div className="flow-invoice">
        <div className="flow-invoice__head">
          <span className="flow-invoice__brand">{hero.invoiceBrand}</span>
          <span className={`chip ${isExpense ? "chip--gold" : "chip--red"}`}>
            {chipLabel}
          </span>
        </div>
        <div className="flow-invoice__row">
          <span>{invoiceName}</span>
          <span className="flow-invoice__amount">{invoiceAmount}</span>
        </div>
        {result?.mock && (
          <span className="chip chip--gold hero-demo__mock">{hero.mockNote}</span>
        )}
        <span className="stamp">{confirmed ? hero.stamp : result ? hero.stampPending : hero.stamp}</span>
      </div>

      {result?.confirmation && (
        <p className="hero-demo__reply urdu" lang="ur" dir="rtl">
          {result.confirmation}
        </p>
      )}
      {phase === "result" && serverReply && (
        <p className="hero-demo__reply urdu" lang="ur" dir="rtl">
          {serverReply}
        </p>
      )}

      {phase === "result" && result && result.buttons.length > 0 && (
        <div className="hero-demo__quick" role="group" aria-label={`${hero.confirmBtn} / ${hero.changeBtn}`}>
          <button
            type="button"
            className="hero-demo__quick-btn hero-demo__quick-btn--confirm"
            disabled={busy}
            onClick={() => pressQuickReply("confirm")}
          >
            <CheckIcon /> {hero.confirmBtn}
          </button>
          <button
            type="button"
            className="hero-demo__quick-btn hero-demo__quick-btn--change"
            disabled={busy}
            onClick={() => pressQuickReply("correct")}
          >
            <PencilIcon /> {hero.changeBtn}
          </button>
        </div>
      )}

      {(phase === "result" || phase === "rejected" || phase === "error") && (
        <button
          type="button"
          className="hero-demo__reset"
          onClick={reset}
          disabled={busy || recording}
        >
          {hero.sendAnother}
        </button>
      )}

      <div className="hero-demo__links">
        <a className="demo-frame__link" href="/ledger">
          {hero.link} <ArrowIcon />
        </a>
        <a className="demo-frame__link" href="/simulator">
          {hero.chatLink} <ArrowIcon />
        </a>
      </div>
    </div>
  );
}

export default function App() {
  const copy = COPY;
  const revealRef = useReveal();

  return (
    <>
      <a className="skip-link" href="#main">
        {copy.a11y.skip}
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
          <nav className="site-nav" aria-label={copy.a11y.nav}>
            <a href="#problem">{copy.nav.problem}</a>
            <a href="#how">{copy.nav.how}</a>
            <a href="#why">{copy.nav.why}</a>
            <a href="#trust">{copy.nav.trust}</a>
          </nav>
          <div className="header-actions">
            <SfxToggle labelOn={copy.mithu.sfxOn} labelOff={copy.mithu.sfxOff} />
            <a className="btn btn--primary header-cta" href="/ledger">
              {copy.nav.cta}
            </a>
          </div>
        </div>
      </header>

      <main id="main" ref={revealRef}>
        {/* ---------------- HERO ---------------- */}
        <section className="hero wrap" id="top" aria-labelledby="hero-heading">
          <div className="hero__grid">
            <div className="reveal">
              <p style={{ margin: 0 }}>
                <span className="sticker">{copy.hero.sticker}</span>
              </p>
              <h1 id="hero-heading">
                {copy.hero.h1Pre}
                <span className="hl">{copy.hero.h1Hl}</span>
                {copy.hero.h1Post}
              </h1>
              <p className="lede">{copy.hero.lede}</p>
              <div className="cta-row">
                <a className="btn btn--primary" href="/ledger">
                  {copy.hero.ctaPrimary}
                </a>
                <a className="btn btn--ghost" href="#how">
                  {copy.hero.ctaSecondary}
                </a>
              </div>
            </div>

            {/* Mithu presents the frame — feet planted on its top edge */}
            <div className="hero__demo reveal">
              <div className="hero__mithu mithu--bob">
                <GuideMithu
                  tips={copy.mithu.tips}
                  size={150}
                  label={copy.mithu.heroLabel}
                  bubbleLabel={copy.mithu.bubbleLabel}
                />
              </div>

              {/* The live demo — a real voice note into the real webhook */}
              <DemoFrame hero={copy.hero} />
              <p className="hero-demo__note">{copy.hero.freeTierNote}</p>
            </div>
          </div>
        </section>

        {/* ---------------- SCROLL MOVIE ---------------- */}
        <LazyScrollMovie />

        {/* ---------------- PROBLEM ---------------- */}
        <section className="section" id="problem" aria-labelledby="problem-heading">
          <div className="wrap">
            <div className="section-head reveal">
              <span className="chip chip--red">{copy.problem.chip}</span>
              <h2 id="problem-heading">{copy.problem.h2}</h2>
              <p className="sticker-row">
                <span className="sticker">{copy.problem.sticker}</span>
                <span className="mithu-guide mithu--bob">
                  <Mithu mood="clarify" size={80} />
                </span>
              </p>
            </div>

            <div className="stats">
              {copy.problem.stats.map((s) => (
                <article className="card stat reveal" key={s.chip}>
                  <span className={`chip chip--${s.tone}`}>{s.chip}</span>
                  <div className={s.isWord ? "stat__word" : `stat__num stat__num--${s.tone}`}>
                    {s.num}
                  </div>
                  <p>{s.text}</p>
                </article>
              ))}
            </div>

            <article className="card mawakmat-card reveal">
              <div>
                <span className="chip chip--green">
                  <BankIcon width="16" height="16" /> {copy.problem.mawakhat.chip}
                </span>
                <h3>{copy.problem.mawakhat.h3}</h3>
                <p>{copy.problem.mawakhat.p}</p>
              </div>
              <div>
                <dl className="mini-stats">
                  {copy.problem.mawakhat.minis.map((m) => (
                    <div className="mini-stat" key={m.dt}>
                      <dt>{m.dt}</dt>
                      <dd>{m.dd}</dd>
                    </div>
                  ))}
                </dl>
                <p className="fine">{copy.problem.mawakhat.fine}</p>
              </div>
            </article>
          </div>
        </section>

        {/* ---------------- HOW IT WORKS ---------------- */}
        <section className="section" id="how" aria-labelledby="how-heading">
          <div className="wrap">
            <div className="section-head reveal">
              <span className="chip chip--green">{copy.how.chip}</span>
              <h2 id="how-heading">{copy.how.h2}</h2>
              <p className="sticker-note">
                <span className="sticker">{copy.how.sticker}</span>
              </p>
            </div>

            <div className="steps">
              {copy.how.steps.map((st, i) => {
                const tone = ["green", "gold", "teal"][i];
                const Tile = [MicIcon, CameraIcon, ReportIcon][i];
                return (
                  <article className="card step reveal" key={st.h3}>
                    <div className="step__top">
                      <span className={`chip chip--${tone}`}>{st.chip}</span>
                      <span className={`icon-tile icon-tile--${tone}`}>
                        <Tile />
                      </span>
                    </div>
                    <h3>{st.h3}</h3>
                    <p>{st.p}</p>
                    <div className="step__badges">
                      <span className="chip chip--gold">{st.badges[0]}</span>
                      <span className="chip">{st.badges[1]}</span>
                    </div>
                  </article>
                );
              })}
            </div>
          </div>
        </section>

        {/* ---------------- DIFFERENTIATORS ---------------- */}
        <section className="section" id="why" aria-labelledby="why-heading">
          <div className="wrap">
            <div className="section-head reveal">
              <span className="chip chip--red">{copy.why.chip}</span>
              <h2 id="why-heading">{copy.why.h2}</h2>
              <p className="sticker-note">
                <span className="sticker">{copy.why.sticker}</span>
              </p>
            </div>

            <div className="diff-grid">
              {copy.why.cards.map((card, i) => {
                const tone = ["red", "green", "gold"][i];
                const Tile = [RadarIcon, TrailIcon, BankIcon][i];
                return (
                  <article className="card diff reveal" key={card.h3}>
                    <span className={`icon-tile icon-tile--${tone}`}>
                      <Tile />
                    </span>
                    <h3>{card.h3}</h3>
                    <p>
                      {card.pPre}
                      {card.pStrong && <strong>{card.pStrong}</strong>}
                      {card.pPost}
                    </p>
                    <span className={`chip chip--${tone} diff__tag`}>{card.tag}</span>
                  </article>
                );
              })}
            </div>
          </div>
        </section>

        {/* ---------------- TRUST / AUDIT ---------------- */}
        <section className="section band" id="trust" aria-labelledby="trust-heading">
          <div className="wrap">
            <div className="band-grid">
              <div className="section-head reveal">
                <span className="chip chip--gold">{copy.trust.chip}</span>
                <h2 id="trust-heading">{copy.trust.h2}</h2>
                <div className="rule" aria-hidden="true" />
                <p className="lede">{copy.trust.lede}</p>
              </div>

              <div className="reveal">
                <div className="ledger-mock-row">
                  {/* Mock preview of the dashboard's stamp language */}
                  <div className="card ledger-mock" aria-label="Mock preview of one audited ledger entry">
                    <div className="ledger-mock__head">
                      <span className="ledger-mock__title">
                        <MicIcon width="18" height="18" /> {copy.trust.mock.title}
                      </span>
                      <span className="chip chip--red">{copy.trust.mock.creditChip}</span>
                    </div>

                    <div className="ledger-mock__row">
                      <div>
                        <div className="ledger-mock__name">{copy.trust.mock.name}</div>
                      </div>
                      <span className="ledger-mock__amount">{copy.trust.mock.amount}</span>
                    </div>

                    <ul className="ledger-mock__meta">
                      <li>
                        <MicIcon width="18" height="18" />
                        {copy.trust.mock.source}
                      </li>
                      <li>
                        <TrailIcon width="18" height="18" />
                        {copy.trust.mock.parsed}
                      </li>
                    </ul>

                    <span className="ledger-mock__correct">
                      <PencilIcon /> {copy.trust.mock.correct}
                    </span>
                    <span className="stamp ledger-mock__stamp">{copy.trust.mock.stamp}</span>
                  </div>
                  <span className="mithu-guide mithu--bob">
                    <Mithu mood="success" size={96} />
                  </span>
                </div>
                <p className="mock-caption">{copy.trust.mock.caption}</p>

                <div className="band-ctas">
                  <a className="btn btn--ghost" href="/ledger">
                    {copy.trust.ctaLedger}
                  </a>
                  <a className="btn btn--ghost" href="/credit">
                    {copy.trust.ctaReport}
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
              <p className="footer-tagline">{copy.footer.tagline}</p>
            </div>

            <p className="footer-credits">
              {copy.footer.credits1}
              <br />
              {copy.footer.credits2}
            </p>

            <nav className="footer-links" aria-label="Live demo">
              <a href="/ledger">
                {copy.footer.linkLedger} <ArrowIcon />
              </a>
              <a href="/credit">
                {copy.footer.linkReport} <ArrowIcon />
              </a>
            </nav>
          </div>

          <p className="honesty">{copy.footer.honesty}</p>
        </div>
      </footer>
    </>
  );
}
