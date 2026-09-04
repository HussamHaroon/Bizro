/* Mithu guide copy — rotating bubble tips + SFX-toggle labels.

   Standalone module on purpose: it imports NOTHING (not content.ts, not
   React) so the orchestrator can merge these strings into content.ts's
   `mithu` section and hand them to GuideMithu / SfxToggle as props.

   Language law (owner directive 2026-09-04): the site is ENGLISH-ONLY.
   Short, friendly sentences a first-time visitor reads at a glance. */

export interface MithuGuideCopy {
  /** Four rotating guide tips. Each bubble-open shows the next one, cycling. */
  tips: string[];
  /** aria-label for the speech-bubble container. */
  bubbleLabel: string;
  /** SfxToggle word label while sound is ON. */
  sfxOn: string;
  /** SfxToggle word label while sound is OFF. */
  sfxOff: string;
}

export const MITHU_COPY: MithuGuideCopy = {
  tips: [
    "Send a voice note — I do the typing.",
    "Got a receipt photo? I'll read it.",
    "Every entry gets a stamp.",
    "Your ledger becomes your credit history.",
  ],
  bubbleLabel: "Mithu's guide tip",
  sfxOn: "Sound on",
  sfxOff: "Sound off",
};
